from fastapi import FastAPI
from src.api.router import router
from src.services.redis import redis_service
from src.config.settings import settings

app= FastAPI(
    title= settings.APP_NAME,
    debug= settings.DEBUG,
    version= "1.0.0"
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    print(f"{settings.APP_NAME} is starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down. Closing infrastructure connections...")
    await redis_service.close()

@app.get("/")
async def health_check():
    return {
        "status": "online",
        "engine": "BatchProcure AI Aggregator",
        "version": "1.0.0"
    }