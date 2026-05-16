from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.db import get_session
from src.services.redis import redis_service
from src.agents.normalizer import normalizer_agent
from src.agents.predictor import predictor_agent
from src.models.orders import OrderPool, Intent, PoolStatus
from pydantic import BaseModel

router= APIRouter(prefix= "/api/v1", tags=["Aggregator"])

class IntentRequest(BaseModel):
    restaurant_id: str
    raw_product_name: str
    quantity: float
    zip_code: str
    price_limit: float

@router.post("/intents")
async def submit_intent(request: IntentRequest, db: AsyncSession= Depends(get_session)):
    # 1. AI Normalization (Turn 'Atta' -> 'wheat_flour')
    normalized= await normalizer_agent.normalize(request.raw_product_name)

    # 2. Redis Key for the Pool
    pool_key= f"pool:{normalized.canonical_id}:{request.zip_code}"

    # 3. Check if we need to initialize a new pool
    current_pool= await redis_service.hgetall(pool_key)
    prediction= None

    if not current_pool:
        # First time this product is ordered in this area!
        # Trigger the Prediction Agent (Cold Start logic)
        prediction= await predictor_agent.predict_aggregation_speed(
            request.zip_code, normalized.canonical_name
        )

        # Initialize Redis Hash
        await redis_service.set(f"{pool_key}:meta", {
            "prediction": prediction.model_dump(),
            "canonical_name": normalized.canonical_name
        })

    # 4. Atomic Increment in Redis (No race conditions!)
    new_total= await redis_service.hincrby_float(pool_key, "total", request.quantity)

    # 5. Persist Intent to Postgres (Audit Trail)
    # Note: In a real 'Monster' app, we'd do this in a background task, 
    # but for now we keep it in-line for simplicity.
    new_intent= Intent(
        restaurant_id= request.restaurant_id,
        quantity= request.quantity,
        price_limit= request.price_limit
    )
    db.add(new_intent)
    await db.commit()

    return {
        "status": "success",
        "normalized_as": normalized.canonical_name,
        "pool_total": new_total,
        "prediction": prediction if prediction else "Already aggregating"
    }