from fastapi import FastAPI 
from src.services.redis import redis_service
from src.config.settings import settings

app= FastAPI(
    title= settings.PROJECT_NAME,
    description= "Scalable AI Engine for Supplier Verification",
    version= "0.1.0"
)

@app.on_event("startup")
async def startup_event():
    """ 
    Warm up the infrastructure: 
    Connects to Redis before the first request hits the server.
    """
    await redis_service.connect()
    print("App Startup: Redis Connected")

@app.on_event("shutdown")
async def shutdown_event():
    """ Graceful shutdown to prevent data corruption during 10k-user loads """
    await redis_service.disconnect()
    print("App Shutdown: Connection Closed")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}