import pytest    # type: ignore
from fastapi.testclient import TestClient   # type: ignore
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.main import app
from src.models.orders import OrderPool, PoolStatus

def test_websocket_handshake_and_broadcast():
    """
    Verifies that the WebSocket endpoint accepts connections, performs the
    initial database handshake, and forwards Redis Pub/Sub events to the client.
    """
    client = TestClient(app)
    
    # 1. Setup mock order pool data
    mock_pool = OrderPool(
        id=42,
        product_name="Whole Wheat Flour",
        canonical_product_id="wheat_flour",
        zip_code="400001",
        target_quantity=100.0,
        current_quantity=50.0,
        status=PoolStatus.OPEN
    )
    
    # 2. Mock AsyncSessionLocal execute results
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_pool
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    
    # Context manager mock for AsyncSessionLocal
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    
    # 3. Mock Redis pubsub object and listen generator
    mock_pubsub = AsyncMock()
    
    # Simulate a single live update message streamed from Redis Pub/Sub
    async def mock_listen():
        yield {
            "type": "message",
            "data": '{"pool_id": 42, "current_quantity": 60.0, "status": "open", "message": "New intent added"}'
        }
        # Connection closes after yielding the first mock update
    
    mock_pubsub.listen = mock_listen
    
    # 4. Patch imports inside src.api.main
    with patch("src.api.main.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("src.api.main.redis_service.client.pubsub", return_value=mock_pubsub):
        
        # Connect to the WebSocket
        with client.websocket_connect("/ws/pools/42") as websocket:
            # Check Handshake payload
            initial_data = websocket.receive_json()
            assert initial_data["pool_id"] == 42
            assert initial_data["product_name"] == "Whole Wheat Flour"
            assert initial_data["current_quantity"] == 50.0
            assert initial_data["target_quantity"] == 100.0
            assert initial_data["status"] == "open"
            assert "Connected" in initial_data["message"]
            
            # Check Broadcast update payload
            broadcast_data = websocket.receive_json()
            assert broadcast_data["pool_id"] == 42
            assert broadcast_data["current_quantity"] == 60.0
            assert broadcast_data["status"] == "open"
            assert "New intent added" in broadcast_data["message"]
