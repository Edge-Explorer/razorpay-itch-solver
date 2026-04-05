import redis.asyncio as redis
from src.config.settings import settings
from typing import Optional

class RedisService:
    """
    The High-Speed Caching Layer. 
    Handles task results and semantic caching to ensure our system remains 
    responsive during massive 10k-user spikes.
    """
    def __init__(self):
        self.client: Optional[redis.Redis]= None
    
    async def connect(self):
        """ 
        Initializes the asynchronous Redis connection from our global settings.
        Decodes responses into UTF-8 strings automatically for easier handling.
        """
        if not self.client:
            self.client= await redis.from_url(
                settings.REDIS_URL,
                decode_responses= True # Automatically converts bytes to Python strings
            )
        return self.client
    
    async def disconnect(self):
        """ Cleanly shuts down the Redis connection for a graceful system exit """
        if self.client:
            await self.client.close()
            self.client= None

# Singleton instance for the entire application
redis_service= RedisService()