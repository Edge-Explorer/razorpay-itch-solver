import asyncio
from typing import List 
from celery import shared_task
from src.workers.celery_app import worker_app
from src.services.db import async_session
from src.utils.concurrency import distributed_lock
from src.utils.adapters import WalletMockProvider, PorterMockProvider
from src.models.orders import OrderPool, PoolStatus
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Instantiate our Provider Adapters
payment_service= WalletMockProvider()
logistics_service= PorterMockProvider()

# Helper to run async code inside Celery's synchronous worker threads
def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@worker_app.task(name="tasks.process_pool_dispatch")
def process_pool_dispatch(pool_id: int):
    """
    Background worker task responsible for locking, charging, and booking logistics
    for a completed wholesale procurement pool.
    """
    return run_async(_process_pool_dispatch_async(pool_id))

async def _process_pool_dispatch_async(pool_id: int) -> dict:
    # 1. Acquire distributed lock for safety (no double bookings!)
    async with distributed_lock(f"dispatch:pool:{pool_id}", lease_time_ms=30000):
        async with async_session() as db:
            # 2. Fetch the pool and load all its linked intents
            query=(
                select(OrderPool)
                .where(OrderPool.id==pool_id)
                .options(selectinload(OrderPool.intents))
            )
            results= await db.execute(query)
            pool= results.scalar_one_or_none()

            if not pool:
                return {"status": "failed", "reason": "Pool not found"}
            if pool.status!= PoolStatus.DRAFT:
                return {"status": "skipped", "reason": f"Pool already in {pool.status.value} status"}

            # 3. Transition status to prevent any incoming updates
            pool.status= PoolStatus.LOCKED
            await db.commit()

            print(f"Pool {pool_id} successfully locked. Begning settlement pipeline...")

            # 4. Charge restaurants concurrently
            payment_tasks=[]
            for intent in pool.intents:
                charge_amount= intent.quantity * intent.price_limit
                payment_tasks.append(
                    payment_service.capture_payment(intent.restaurant_id, charge_amount)
                )
            payment_results= await asyncio.gather(*payment_tasks, return_exceptions=True)

            # Verify payments
            for res in payment_results:
                if isinstance(res, Exception) or res.get("status")!= "captured":
                    pool.status= PoolStatus.DRAFT
                    await db.commit()
                    return{"status": "failed", "reason": "Payment capture failed for one or more restaurants."}

            # 5. Book Logistics
            total_weight= sum(intent.quantity for intent in pool.intents)
            # Call Porter Adapter to get Quote & Book delivery
            quote= await logistics_service.get_delivery_quote(
                origin= "Wholesale Central Warehouse, Navi Mumbai",
                destination= f"ZIP Area Cluster {pool_id}", # Destination cluster
                weight_kg= total_weight
            )

            booking= await logistics_service.book_delivery(quote["quote_id"])

            # 6. Complete Transition
            pool.status= PoolStatus.FULFILLED
            await db.commit()
            print(f"Pool {pool_id} fully settled & dispatched! Porter Booking: {booking['booking_id']}")

            return {
                "status": "success",
                "pool_id": pool_id,
                "driver_name": booking["driver_name"],
                "eta_minutes": booking["eta_minutes"],
                "tracking_id": booking["tracking_id"]
            }