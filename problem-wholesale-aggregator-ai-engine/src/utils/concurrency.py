import asyncio
import uuid
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from src.services.redis import redis_service

class DistributedLockError(Exception):
    """Raised when a distributed lock cannot be acquired within the timeout window."""
    pass

class RedisDistributedLock:
    """
    High-concurrency distributed lock implementation using Redis.
    Ensures safe, atomic state transitions across multiple stateless API instances.
    """
    def __init__(self, lock_key: str, lease_time_ms: int= 10000, acquire_timeout_ms: int= 5000) -> None:
        self.lock_key= f"lock:{lock_key}"
        self.lease_time_ms= lease_time_ms
        self.acquire_timeout_ms= acquire_timeout_ms
        # Generate a unique client identifier to ensure safe releases
        self.client_id= str(uuid.uuid4())

    async def acquire(self) -> bool:
        """
        Attempts to acquire the lock using Redis SET with NX and PX options.
        Includes a retry loop to poll until the lock is freed or timeout is reached.
        """
        end_time= asyncio.get_event_loop().time() + (self.acquire_timeout_ms / 1000.0)

        while asyncio.get_event_loop().time() < end_time:
            # SET key value NX (only if not exists) PX lease_time (auto-expire)
            acquired= await redis_service.client.set(
                self.lock_key,
                self.client_id,
                nx= True,
                px= self.lease_time_ms
            )
            if acquired:
                return True
            # Backoff briefly to avoid hammering Redis
            await asyncio.sleep(0.05)

        return False

    async def release(self) -> None:
        """
        Releases the lock. Uses a Lua script to guarantee atomicity:
        ONLY release if the client_id matches (prevents releasing someone else's lock).
        """
        lua_release_script="""
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        await redis_service.client.eval(lua_release_script, 1, self.lock_key, self.client_id)

@asynccontextmanager
async def distributed_lock(lock_key: str, lease_time_ms: int= 10000, acquire_timeout_ms: int= 5000) -> AsyncGenerator[None, None]:
    """
    Convenient context manager wrapper.
    Usage:
        async with distributed_lock("pool_123"):
            # Critical Section here
    """
    lock= RedisDistributedLock(lock_key, lease_time_ms, acquire_timeout_ms)
    acquired= await lock.acquire()
    if not acquired:
        raise DistributedLockError(f"Could not acquire lock for resource: {lock_key}")

    try:
        yield
    finally:
        await lock.release()