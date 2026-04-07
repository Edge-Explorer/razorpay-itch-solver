import asyncio
import json
from src.services.db import AsyncSessionLocal
from src.workers.celery_app import worker_app
from src.models.supplier import Supplier
from src.agents.researcher import ResearcherAgent 
from sqlalchemy import select
from src.utils.parsers import parse_json_report

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
    ai_report= parse_json_report(ai_raw_result)

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
            supplier.risk_score = ai_report.get("risk_score", 0.5)
            supplier.summary = ai_report.get("summary", "N/A")
    
    save_local_report(entity_id, ai_report)
    return {"status": "success", "entity_id": entity_id}

def save_local_report(entity_id, report):
    """ Saves a systematic JSON snapshot of the audit """
    reports_dir= "data/reports"
    os.makedirs(reports_dir, exist_ok= True)

    file_path= f"{reports_dir}/{entity_id}.json"
    with open(file_path, "w", encoding= "utf-8") as f:
        json.dump(report, f, indent= 4, ensure_ascii= False)