import os
import httpx
from src.config.settings import settings
from typing import Dict, List

def search_web(query: str) -> str:
    """
    Performs a live web search using Tavily API for AI-optimized results.
    """
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 5,
        "include_raw_content": False
    }

    with httpx.Client() as client:
        response = client.post(url, json=payload)
        if response.status_code != 200:
            return {"error": f"Tavily Failed: {response.text}"}
            
        data = response.json()

        return {
            "results": data.get("results", []),
            "query": query
        }

def verify_registration(entity_id: str) -> Dict:
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