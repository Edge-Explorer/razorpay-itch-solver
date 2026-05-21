from fastapi import APIRouter, Depends, HTTPException  # type: ignore[import]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.db import get_session
from src.services.redis import redis_service
from src.agents.normalizer import normalizer_agent
from src.agents.predictor import predictor_agent
from src.agents.qa_analyzer import qa_agent
from src.models.orders import OrderPool, Intent, PoolStatus
from src.models.disputes import Dispute, DisputeStatus, DisputeSeverity
from src.models.suppliers import Product
from src.utils.concurrency import distributed_lock, DistributedLockError
from src.utils.adapters import WalletMockProvider
from src.workers.tasks import process_pool_dispatch
from pydantic import BaseModel


router= APIRouter(prefix= "/api/v1", tags=["Aggregator"])
payment_service= WalletMockProvider()

class IntentRequest(BaseModel):
    restaurant_id: str
    raw_product_name: str
    quantity: float
    zip_code: str
    price_limit: float
    
class DisputeRequest(BaseModel):
    pool_id: int
    restaurant_id: str
    supplier_id: int
    description: str
    pickup_notes: str
    dropoff_notes: str
    evidence_url: str | None= None
    
# ==========================================
# 1. INTENT SUBMISSION ENDPOINT (Aggregation)
# ==========================================
@router.post("/intents")
async def submit_intent(request: IntentRequest, db: AsyncSession = Depends(get_session)):
    # 1. AI Normalization (Turn 'Atta' -> 'wheat_flour')
    normalized = await normalizer_agent.normalize(request.raw_product_name)

    # 2. Redis Key for the Pool
    pool_key = f"pool:{normalized.canonical_id}:{request.zip_code}"
    
    try:
        # 3. Acquire Distributed Lock (Redlock pattern)
        async with distributed_lock(f"pool_lock:{normalized.canonical_id}:{request.zip_code}", lease_time_ms=10000):
            
            # 4. Query for an existing OPEN pool
            query = (
                select(OrderPool).where(
                    OrderPool.canonical_product_id == normalized.canonical_id, 
                    OrderPool.zip_code == request.zip_code, 
                    OrderPool.status == PoolStatus.OPEN
                )
            )
            result = await db.execute(query)
            pool = result.scalar_one_or_none() # Fixed typo here (singular 'scalar')
            
            # 5. Initialize new pool if none exists
            prediction = None
            if not pool:
                # Cold Start Prediction
                prediction = await predictor_agent.predict_aggregation_speed(
                    request.zip_code, normalized.canonical_name
                )
                
                # Fetch MOQ threshold from products catalog
                prod_query = select(Product).where(Product.name == normalized.canonical_name)
                prod_res = await db.execute(prod_query)
                product = prod_res.scalar_one_or_none()
                target_moq = product.moq_threshold if product else 100.0 # Fallback default
                
                pool = OrderPool(
                    product_name=normalized.canonical_name,
                    canonical_product_id=normalized.canonical_id,
                    zip_code=request.zip_code,
                    target_quantity=target_moq,
                    current_quantity=0.0,
                    status=PoolStatus.OPEN
                )
                db.add(pool)
                await db.flush() # Generates pool.id
                
                # Cache prediction and details in Redis for WebSocket/API reads
                await redis_service.set(f"{pool_key}:meta", {
                    "prediction": prediction.model_dump(),
                    "canonical_name": normalized.canonical_name
                })
                
            # 6. Create the Intent and update pool quantity (UN-INDENTED to run for all cases)
            new_intent = Intent(
                pool_id=pool.id,
                restaurant_id=request.restaurant_id,
                quantity=request.quantity,
                price_limit=request.price_limit
            )
            db.add(new_intent)
            
            pool.current_quantity += request.quantity
            
            # 7. Check MOQ Threshold (MOQ triggered dispatch)
            dispatched = False
            if pool.current_quantity >= pool.target_quantity:
                pool.status = PoolStatus.SOFT_LOCK
                dispatched = True
                # Trigger Celery Dispatch Task in background
                process_pool_dispatch.delay(pool.id)
            
            await db.commit()
            
            # 8. Sync current total in Redis for fast access
            await redis_service.set(pool_key, {
                "total": pool.current_quantity,
                "status": pool.status.value,
                "target": pool.target_quantity
            })

            # 9. Broadcast live update to WebSockets
            await redis_service.publish(
                f"pool_broadcast:{pool.id}",
                {
                    "pool_id": pool.id,
                    "product_name": pool.product_name,
                    "current_quantity": pool.current_quantity,
                    "target_quantity": pool.target_quantity,
                    "status": pool.status.value,
                    "progress_pct": (pool.current_quantity / pool.target_quantity) * 100 if pool.target_quantity else 0,
                    "message": f"New intent added: {request.quantity} kg of {normalized.canonical_name}."
                }
            )
            
            return {
                "status": "success",
                "pool_id": pool.id,
                "normalized_as": normalized.canonical_name,
                "pool_total": pool.current_quantity,
                "target_moq": pool.target_quantity,
                "dispatched": dispatched,
                "prediction": prediction if prediction else "Already aggregating"
            }

    except DistributedLockError:
        raise HTTPException(
            status_code=423,
            detail="Resource locked. Another intent for this pool is currently being processed."
        )
        
# ==========================================
# 2. DISPUTE TRIAGING ENDPOINT (QA AI Agent)
# ==========================================
@router.post("/disputes")
async def submit_dispute(request: DisputeRequest, db: AsyncSession= Depends(get_session)):
    # 1. Trigger the QA AI Agent to perform three-way triage
    analysis= await qa_agent.triage_dispute(
        description= request.description, 
        pickup_notes= request.pickup_notes,
        dropoff_notes= request.dropoff_notes
    )
    
    # Convert AI string outputs to database enum classes
    status_mapping= {
        "resolved_in_favor_of_buyer": DisputeStatus.RESOLVED_IN_FAVOR_OF_BUYER,
        "resolved_in_favor_of_supplier": DisputeStatus.RESOLVED_IN_FAVOR_OF_SUPPLIER,
        "logistics_fault": DisputeStatus.LOGISTICS_FAULT
    }
    
    severity_mapping= {
        "low": DisputeSeverity.LOW,
        "medium": DisputeSeverity.MEDIUM,
        "high": DisputeSeverity.HIGH
    }
    
    final_status= status_mapping.get(analysis.suggested_status, DisputeStatus.UNDER_REVIEW)
    final_severity= severity_mapping.get(analysis.suggested_severity, DisputeSeverity.LOW)
    
    # 2. Persist the dispute to database (Audit Trail)
    new_dispute= Dispute(
        pool_id= request.pool_id,
        restaurant_id= request.restaurant_id,
        supplier_id= request.supplier_id,
        description= request.description,
        evidence_url= request.evidence_url,
        status= final_status,
        severity= final_severity,
        confidence_score= analysis.confidence_score,
        resolution_notes= analysis.reasoning
    )
    db.add(new_dispute)
    await db.commit()
    
    # 3. Automated Refund Trigger (If supplier or transporter is at fault)
    refund_status= "none"
    if final_status in [DisputeStatus.RESOLVED_IN_FAVOR_OF_BUYER, DisputeStatus.LOGISTICS_FAULT]:
        refund_res= await payment_service.refund_payment(
            transaction_id= f"tx_mock_{request.pool_id}",
            amount= 1500.0
        )
        refund_status= refund_res["status"]
        
    return {
        "status": "processed",
        "analysis": {
            "suggested_status": final_status.value,
            "suggested_severity": final_severity.value,
            "confidence_score": analysis.confidence_score,
            "reasoning": analysis.reasoning
        },
        "refund_status": refund_status
    }