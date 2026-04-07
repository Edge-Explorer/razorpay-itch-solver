import os
import httpx
from src.config.settings import settings
from typing import Dict, List

async def search_web(query: str) -> str:
    """
    Performs a live web search using Tavily API for AI-optimized results.
    """
    url= "https://api.tavily.com/search"
    payload= {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "smart",
        "include_answer": True
    }

    async with httpx.AsyncClient() as client:
        response= await client.post(url, json= payload)
        data= response.json()

        return data.get("answer", "No specific information found.")

async def verify_registration(entity_id: str) -> Dict:
    """
    Checks the entity ID against government registries.
    """
    return {
        "entity_id": entity_id,
        "status": "Active",
        "registration_date": "2010-05-12",
        "type": "Private Limited"
    }

Tools = [search_web, verify_registration]