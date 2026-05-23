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
import json
from src.agents.normalizer import NormalizedProduct
from fastapi import File, Form, UploadFile   # type: ignore[import]
from src.services.cloudinary import cloudinary_service
from src.agents.verifier import document_verifier_agent
from src.models.suppliers import Supplier, VerificationStatus
import asyncio


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
    # 1. Check Redis Cache for AI Normalization first
    raw_name_key = request.raw_product_name.lower().strip()
    cache_key = f"normalized_product:{raw_name_key}"
    
    try:
        cached_norm = await redis_service.get(cache_key)
        if cached_norm:
            normalized_data = json.loads(cached_norm)
            normalized = NormalizedProduct(**normalized_data)
            print(f"[CACHE HIT] Normalization for '{request.raw_product_name}' -> '{normalized.canonical_name}' fetched from Redis.")
        else:
            normalized = await normalizer_agent.normalize(request.raw_product_name)
            # Cache for 7 days (604800 seconds)
            await redis_service.set(cache_key, normalized.model_dump(), ex=604800)
            print(f"[CACHE MISS] Normalization for '{request.raw_product_name}' -> '{normalized.canonical_name}' fetched from Gemini and Cached.")
    except Exception as e:
        print(f"Warning: Cache failed or bypassed for Normalization: {e}")
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
            pool = result.scalar_one_or_none()
            
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
                
            # 6. Create the Intent and update pool quantity
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

# ==========================================
# 3. SUPPLIER REGISTRATION ENDPOINT (OCR + CDN)
# ==========================================
@router.post("/suppliers/register")
async def register_supplier(name: str= Form(...), contact_email: str= Form(...), pan_number: str= Form(...), aadhar_number: str= Form(...), pan_image: UploadFile= File(...), aadhar_image: UploadFile= File(...), db: AsyncSession= Depends(get_session)):
    """
    Registers a wholesale supplier, uploads their identity documents (PAN & Aadhaar) 
    to Cloudinary CDN, runs multimodal Gemini OCR verification, and saves the outcome.
    """
    # 1. Read uploaded image streams into memory bytes
    try:
        pan_bytes= await pan_image.read()
        aadhar_bytes= await aadhar_image.read()
    except Exception as e:
        raise HTTPException(status_code= 400, detail= f"Failed to read image files: {str(e)}")
    
    # 2. Upload both documents to Cloudinary concurrently
    try:
        pan_upload_task= cloudinary_service.upload_image(pan_bytes, folder= "pan_documents")
        aadhar_upload_task= cloudinary_service.upload_image(aadhar_bytes, folder= "aadhar_documents")
        pan_url, aadhar_url= await asyncio.gather(pan_upload_task, aadhar_upload_task)
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Failed to upload documents to Cloudinary CDN: str{str(e)}")
    
    # 3. Trigger Gemini Multimodal OCR verification for both documents concurrently
    try:
        pan_verify_task= document_verifier_agent.verify_document(image_bytes= pan_bytes, mime_type= pan_image.content_type or "image/jpeg", doc_type= "PAN", expected_name= name, expected_number= pan_number)
        aadhar_verify_task= document_verifier_agent.verify_document(image_bytes= aadhar_bytes, mime_type= aadhar_image.content_type or "image/jpeg", doc_type= "Aadhar", expected_name= name, expected_number= aadhar_number)
        pan_result, aadhar_result= await asyncio.gather(pan_verify_task, aadhar_verify_task)
    except Exception as e:
        raise HTTPException(status_code= 500, detail= f"AI document verification failure: str: {str(e)}")
    
    # 4. Decide final verification outcome based on both OCR checks
    is_verified= (pan_result.is_authentic and pan_result.fields_match and aadhar_result.is_authentic and aadhar_result.fields_match)
    status= VerificationStatus.VERIFIED if is_verified else VerificationStatus.REJECTED
    
    audit_notes= (f"PAN Verification: [Authentic={pan_result.is_authentic}, Match={pan_result.fields_match}]. Reasoning:{pan_result.reasoning} |" f"Aadhar Verification: [Authentic= {aadhar_result.is_authentic}, Match= {aadhar_result.fields_match}]. Reasoning:{aadhar_result.reasoning}")
    
    # 5. Persist the Supplier to Neon Postgres
    new_supplier= Supplier(
        name= name,
        contact_email= contact_email,
        pan_number= pan_number,
        aadhar_number= aadhar_number,
        pan_image_url=pan_url,
        aadhar_image_url=aadhar_url,
        verification_status=status,
        verification_comments=audit_notes[:500],  # database column size safety limit
        is_verified=is_verified
    )
    db.add(new_supplier)
    await db.commit()
    await db.refresh(new_supplier)
    
    return {
        "status": "processed",
        "supplier_id": new_supplier.id,
        "verification_status": status.value,
        "is_verified": is_verified,
        "audit_notes": audit_notes,
        "cloudinary_urls": {
            "pan_url": pan_url,
            "aadhar_url": aadhar_url
        }
    }
    
# ==========================================
# 4. SUPPLIER STATUS VERIFICATION CHECK
# ==========================================
@router.get("/suppliers/{supplier_id}/status")
async def get_supplier_status(supplier_id: int, db: AsyncSession= Depends(get_session)):
    """Queries details and verification audit trail of a registered supplier."""
    query= select(Supplier).where(Supplier.id == supplier_id)
    result= await db.execute(query)
    supplier= result.scalar_one_or_none()
    
    if not supplier:
        raise HTTPException(status_code= 404, detail= "Supplier not found")
    
    return {
        "supplier_id": supplier.id,
        "name": supplier.name,
        "contact_email": supplier.contact_email,
        "verification_status": supplier.verification_status.value,
        "is_verified": supplier.is_verified,
        "verification_comments": supplier.verification_comments,
        "pan_image_url": supplier.pan_image_url,
        "aadhar_image_url": supplier.aadhar_image_url
    }

# ==========================================
# 5. LIST ORDER POOLS (For System Dashboard)
# ==========================================
@router.get("/pools")
async def list_pools(db: AsyncSession= Depends(get_session)):
    """Returns a list of all active/fulfilled/failed order pools in the system."""
    query= select(OrderPool)
    result= await db.execute(query)
    pools= result.scalars().all()
    return pools