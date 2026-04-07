import asyncio
import json
from src.services.db import AsyncSessionLocal
from src.workers.celery_app import worker_app
from src.models.supplier import Supplier
from src.agents.researcher import ResearcherAgent 
from sqlalchemy import select

@worker_app.task(bind= True, max_retries= 3)
def verify_supplier_task(self, supplier_name: str, entity_id: str):
    return asyncio.run(process_verification(supplier_name, entity_id))

async def process_verification(name: str, entity_id: str):
    """ The Real-World AI Research Logic """

    # 1. Initialize the AI Auditor Agent
    agent= ResearcherAgent()

    # 2. Run the Gemini Thinking Loop (Real-time research)
    ai_raw_result= await agent.verify_supplier(name, entity_id)

    # 3. Clean and parse the AI JSON
    cleaned_json= ai_raw_result.replace("```json", "").replace("```", "").strip()
    ai_report= json.loads(cleaned_json)

    # 4. Save result to Neon Database (Audit Trail)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stmt = select(Supplier).where(Supplier.entity_id == entity_id)
            
            result = await session.execute(stmt)
            supplier = result.scalar_one_or_none()
            
            if not supplier:
                supplier = Supplier(name=name, entity_id=entity_id)
                session.add(supplier)

            supplier.detailed_report = ai_report
            supplier.risk_score = ai_report.get("risk_score", 0.0)
            supplier.summary = ai_report.get("summary", "No summary provided.")
    return {"status": "success", "entity_id": entity_id}