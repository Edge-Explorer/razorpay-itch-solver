import asyncio
from src.services.db import AsyncSessionLocal
from src.workers.celery_app import worker_app
from src.models.supplier import Supplier
from sqlalchemy import select

@worker_app.task(bind= True, max_retries= 3)
def verify_supplier_task(self, supplier_name: str, entity_id: str):
    """ 
    The background engine that performs the AI verification.
    This runs in our 'Worker Fleet' to keep the API fast.
    """
    return asyncio.run(process_verification(supplier_name, entity_id))

async def process_verification(name: str, entity_id: str):
    """ Core logic for researching and saving a supplier """
    # 1. TODO: Integrate Gemini AI Agent here to do the research
    ai_report= {
        "status": "verified",
        "risk_level": "low",
        "findings": f"Verified {name} - Infrastructure Strong."
    }

    # 2. Save result to Neon Database
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt= select(Supplier).where(Supplier.entity_id == entity_id)
            result= await session.execute(stmt)
            supplier= result.scalar_one_or_none()

            if not supplier:
                supplier= Supplier(name= name, entity_id= entity_id)
                session.add(supplier)

            # Update data with AI findings
            supplier.detailed_report= ai_report
            supplier.risk_score= 0.95
            supplier.summary= ai_report["findings"]

    return {"status": "success", "entity_id": entity_id}