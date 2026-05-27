from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from src.api.router import router
from src.services.redis import redis_service
from src.config.settings import settings
from src.services.db import AsyncSessionLocal
from src.models.orders import OrderPool
from sqlalchemy import select
import json
import os

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    version="1.0.0"
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

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the Control Deck HTML frontend dashboard."""
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard HTML template not found.</h1>", status_code=404)

# ==========================================
# REAL-TIME POOL STATE BROADCAST (WebSockets)
# ==========================================
@app.websocket("/ws/pools/{pool_id}")
async def websocket_pool_tracker(websocket: WebSocket, pool_id: int):
    """
    Subscribes a client to real-time state broadcasts for a specific order pool.
    Pushes an initial state handshake and then pipes events from Redis Pub/Sub.
    """
    await websocket.accept()
    
    # 1. Initialize Redis Pub/Sub connection
    pubsub = redis_service.client.pubsub()
    channel_name = f"pool_broadcast:{pool_id}"
    await pubsub.subscribe(channel_name)
    
    try:
        # 2. Handshake: Fetch and push the current database state of the pool
        async with AsyncSessionLocal() as db:
            query = select(OrderPool).where(OrderPool.id == pool_id)
            res = await db.execute(query)
            pool = res.scalar_one_or_none()
            
            if pool:
                initial_payload = {
                    "pool_id": pool.id,
                    "product_name": pool.product_name,
                    "current_quantity": pool.current_quantity,
                    "target_quantity": pool.target_quantity,
                    "status": pool.status.value,
                    "progress_pct": (pool.current_quantity / pool.target_quantity) * 100 if pool.target_quantity else 0,
                    "message": "Connected to real-time tracker."
                }
                await websocket.send_json(initial_payload)
            else:
                await websocket.send_json({"error": f"Pool with ID {pool_id} not found."})
                await websocket.close(code=1008)
                return

        # 3. Dynamic Broadcast Loop: Pipe Redis Pub/Sub updates directly to the client
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    await websocket.send_json(payload)
                except json.JSONDecodeError:
                    # Fallback for plain string messages
                    await websocket.send_json({"message": message["data"]})
                    
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected from pool {pool_id}")
    except Exception as e:
        print(f"WebSocket error in pool {pool_id}: {str(e)}")
    finally:
        # 4. Graceful Cleanup: Unsubscribe and close Pub/Sub subscription
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()