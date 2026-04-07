from fastapi import FastAPI, Depends, HTTPException
from src.workers.tasks import verify_supplier_task
from src.workers.celery_app import worker_app
from src.services.redis import redis_service
from src.config.settings import settings
from celery.result import AsyncResult

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Scalable AI Engine for Supplier Verification",
    version="0.1.0"
)

@app.on_event("startup")
async def startup_event():
    """ 
    Warm up the infrastructure: 
    Connects to Redis before the first request hits the server.
    """
    await redis_service.connect()
    print("App Startup: Redis Connected")

@app.post("/verify")
async def request_verification(name: str, entity_id: str):
    """ 
    Enqueues a supplier verification job in the background cluster.
    This returns a task_id IMMEDIATELY. Total scalability.
    """
    # .delay() is the magic word: it sends the task to Redis/Celery!
    task = verify_supplier_task.delay(name, entity_id)

    return {
        "message": "Verification started.",
        "task_id": task.id,
        "status": "pending"
    }

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """ Allows the user to poll for the AI research results from Redis """
    task_result = AsyncResult(task_id, app=worker_app)
    
    if task_result.state == "PENDING":
        return {"task_id": task_id, "status": "processing"}
    
    elif task_result.state == "SUCCESS":
        # THE PRO RETURN: Returns the final AI research from Redis
        return {
            "task_id": task_id, 
            "status": "completed", 
            "result": task_result.result
        }
    
    elif task_result.state == "FAILURE":
        return {
            "task_id": task_id, 
            "status": "failed", 
            "error": str(task_result.info)
        }
    
    return {"task_id": task_id, "status": task_result.state}

@app.on_event("shutdown")
async def shutdown_event():
    """ Graceful shutdown to prevent data corruption during 10k-user loads """
    await redis_service.disconnect()
    print("App Shutdown: Connection Closed")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}