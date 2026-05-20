from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.db import get_session
from src.services.redis import redis_service
from src.agents.normalizer import normalizer_agent
from src.agents.predictor import predictor_agent
from src.agents.qa_analyzer import qa_agent
from src.models.orders import OrderPool, Intent, PoolStatus
from src.models.disputes import Dispute, DisputeStatus, DisputeSeverity
from src.utils.adapters import WalletMockProvider
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