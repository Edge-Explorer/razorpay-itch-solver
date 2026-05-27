import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.main import app
from src.services.db import get_session
from src.models.orders import OrderPool, PoolStatus
from src.models.suppliers import Product
from src.agents.predictor import SpeedPrediction

@pytest.mark.asyncio
async def test_concurrent_intent_submissions_redlock():
    """
    Simulates 10 concurrent restaurants submitting intents at the exact same time.
    Verifies that all quantities are aggregated correctly, and the threshold trigger
    dispatches the Celery task EXACTLY ONCE without duplicate dispatches.
    Uses asyncio.Lock to simulate Redlock serialization and checks database pool roll-over behavior.
    """
    # 1. Setup Database Mock and overrides
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    
    # Track all pool objects created in the database
    created_pools = []

    def db_add_mock(obj):
        nonlocal created_pools
        if isinstance(obj, OrderPool):
            created_pools.append(obj)

    # Explicitly mock 'add' as a synchronous MagicMock so its side_effects execute immediately
    mock_db.add = MagicMock()
    mock_db.add.side_effect = db_add_mock
    
    # Configure mock session override
    app.dependency_overrides[get_session] = lambda: mock_db
    
    # 2. Setup mock Product catalog (predefined MOQ)
    mock_product = Product(name="Whole Wheat Flour", moq_threshold=100.0)
    
    mock_result_product = MagicMock()
    mock_result_product.scalar_one_or_none.return_value = mock_product

    # Dynamic execute handler to route mocks based on the executed query statement
    async def dynamic_db_execute(statement, *args, **kwargs):
        nonlocal created_pools
        stmt_str = str(statement).lower()
        
        if "products" in stmt_str:
            return mock_result_product
        elif "order_pools" in stmt_str:
            # Query simulation: Scan our list and only return a pool if it is 'OPEN'
            open_pool = next((p for p in created_pools if p.status == PoolStatus.OPEN), None)
            
            mock_res = MagicMock()
            mock_res.scalar_one_or_none.return_value = open_pool
            return mock_res
        
        return MagicMock()

    mock_db.execute.side_effect = dynamic_db_execute

    # 3. Setup Mock Redis and Real Asyncio Lock for Redlock simulation
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Force cache misses so normalizer runs
    mock_redis.set = AsyncMock()
    mock_redis.publish = AsyncMock()

    # Use a real asyncio.Lock to serialize concurrent requests during the test
    real_lock = asyncio.Lock()

    def mock_distributed_lock(lock_key, lease_time_ms=None):
        class LockContext:
            async def __aenter__(self):
                await real_lock.acquire()
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                real_lock.release()
        return LockContext()

    # Setup mock speed prediction to avoid network calls to Tavily/Gemini
    mock_prediction = SpeedPrediction(
        estimated_hours_to_lock=4,
        confidence_level="High",
        reasoning="High restaurant density in the area."
    )

    # 4. Patch Celery, Normalizer, Predictor, Redis, and Distributed Lock
    with patch("src.api.router.normalizer_agent.normalize", new_callable=AsyncMock) as mock_normalize, \
         patch("src.api.router.predictor_agent.predict_aggregation_speed", new_callable=AsyncMock) as mock_predict_speed, \
         patch("src.api.router.process_pool_dispatch.delay") as mock_celery_delay, \
         patch("src.api.router.redis_service", mock_redis), \
         patch("src.api.router.distributed_lock", side_effect=mock_distributed_lock):
        
        # Setup mock normalizer and predictor outputs
        mock_normalized = MagicMock()
        mock_normalized.canonical_id = "wheat_flour"
        mock_normalized.canonical_name = "Whole Wheat Flour"
        mock_normalize.return_value = mock_normalized
        mock_predict_speed.return_value = mock_prediction

        # Define 10 concurrent requests: each request adds 15kg to the pool
        async def submit_request(client_id):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/v1/intents",
                    json={
                        "restaurant_id": f"rest_{client_id}",
                        "raw_product_name": "Atta",
                        "quantity": 15.0,
                        "zip_code": "400001",
                        "price_limit": 50.0
                    }
                )
                return response

        # Run 10 submissions concurrently
        tasks = [submit_request(i) for i in range(10)]
        responses = await asyncio.gather(*tasks)

        # 5. Assertions
        for resp in responses:
            assert resp.status_code == 200
            assert resp.json()["status"] == "success"

        # Verify that a first pool was successfully created and roll-over created a second one
        assert len(created_pools) == 2

        # First pool gets exactly 7 submissions (7 * 15 = 105kg >= 100kg MOQ)
        assert created_pools[0].current_quantity == 105.0
        assert created_pools[0].status == PoolStatus.SOFT_LOCK

        # Second pool starts and aggregates the remaining 3 submissions (3 * 15 = 45kg)
        assert created_pools[1].current_quantity == 45.0
        assert created_pools[1].status == PoolStatus.OPEN

        # Verify that the Celery dispatch task was triggered EXACTLY ONCE for the locked pool
        assert mock_celery_delay.call_count == 1
        mock_celery_delay.assert_called_once_with(created_pools[0].id)

    # Clean up overrides
    app.dependency_overrides.clear()
