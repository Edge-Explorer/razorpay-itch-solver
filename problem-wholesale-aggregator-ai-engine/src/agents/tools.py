import httpx
from src.config.settings import settings

async def research_area_density(zip_code: str) -> str:
    """
    Uses Tavily Search to find the number of restaurants and food businesses in a specific area.
    This helps the AI 'guess' how fast a group-buy deal will lock.
    """
    url= "https://api.tavily.com/search"

    payload= {
        "api_key": settings.TAVILY_API_KEY,
        "query": f"restaurants and food businesses in pin code {zip_code} India",
        "search_depth": "basic",
        "include_answer": True,
        "max_results": 5
    }

    # We use AsyncClient to keep the "Monster" performance high
    async with httpx.AsyncClient() as client:
        try:
            response= await client.post(url, json= payload)
            response.raise_for_status()
            data= response.json()

            # The 'answer' contains a summary of how many restaurants are in that area
            return data.get("answer") or str(data.get("results"))

        except Exception as e:
            return f"Error researching area: {str(e)}"
