import httpx
from src.config.settings import settings
from src.services.redis import redis_service

async def research_area_density(zip_code: str) -> str:
    """
    Uses Tavily Search to find the number of restaurants and food businesses in a specific area.
    Caches results in Redis for 24 hours to prevent repeated API calls.
    """
    cache_key = f"zip_density:{zip_code}"
    
    # 1. Check Redis Cache first
    try:
        cached_data = await redis_service.get(cache_key)
        if cached_data:
            print(f"[CACHE HIT] Tavily density research for ZIP {zip_code} fetched from Redis.")
            return cached_data
    except Exception as e:
        print(f"Warning: Redis cache lookup failed for ZIP density: {e}")

    # 2. Cache Miss: Run Tavily Search
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": f"restaurants and food businesses in pin code {zip_code} India",
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 5
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[CACHE MISS] Calling Tavily API for ZIP {zip_code} density research...")
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            # The 'answer' contains a summary of how many restaurants are in that area
            result = data.get("answer") or str(data.get("results"))
            
            # 3. Cache the result in Redis for 24 hours (86400 seconds)
            await redis_service.set(cache_key, result, ex=86400)
            return result

        except Exception as e:
            return f"Error researching area: {str(e)}"