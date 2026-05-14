from redis.asyncio import Redis, ConnectionPool
from src.config.settings import settings
import json
from typing import Any 

class RedisService:
    """
    Singleton service managing asynchronous Redis connections, pools,
    atomic hash operations, and Pub/Sub broadcasting.
    """
    def __init__(self) -> None:
        # Create a high-performance async connection pool
        self.pool= ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses= True, # Automatically converts bytes to strings
        )

        self.client= Redis(connection_pool= self.pool)

    async def get(self, key: str) -> Any:
        return await self.client.get(key)
    
    async def set(self, key: str, value: Any, ex: int | None= None) -> None:
        if isinstance(value, (dict, list)):
            value= json.dumps(value)
        await self.client.set(key, value, ex= ex)

    async def hincrby_float(self, name: str, key: str, amount: float) -> float:
        """
        Atomically increments a float value inside a Redis Hash.
        Crucial for preventing race conditions when aggregating demand.
        """
        return await self.client.hincrbyfloat(name, key, amount)

    async def hgetall(self, name: str) -> dict[str, str]:
        return await self.client.hgetall(name)

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """
        Publishes a JSON payload to a specified channel for WebSocket broadcast.
        """
        await self.client.publish(channel, json.dumps(message))

    async def close(self) -> None:
        """Gracefully shuts down active client connections in the pool."""
        await self.client.aclose()

# Global singleton instance
redis_service= RedisService()