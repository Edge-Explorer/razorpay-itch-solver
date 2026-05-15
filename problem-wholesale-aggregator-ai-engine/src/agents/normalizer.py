from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config.settings import settings
import asyncio
import json

class NormalizedProduct(BaseModel):
    """Strict JSON output schema enforced on the Gemini agent."""
    canonical_id: str= Field(description= "Standardized lowercase ID, e.g., wheat_flour, basmati_rice")
    canonical_name: str= Field(description= "Clean, universal product name, e.g., Whole Wheat Flour")
    category: str= Field(description= "Broad ingrediant category, e.g., Grains, Spices, Oils")
    confidence_score: float= Field(description= "Float between 0.0 and 1.0 indicating classification confidence")

class NormalizerAgent:
    """
    Autonomous agent responsible for cleaning and unifying user-submitted ingredient strings
    into wholesale-compatible standard formats.
    """
    def __init__(self) -> None:
        self.client= genai.Client(api_key= settings.GEMINI_API_KEY)
        self.model_name= "gemini-2.0-flash"

    def _normalize_sync(self, raw_input: str) -> NormalizedProduct:
        prompt = f"""
        You are an expert procurement AI for Indian commercial kitchens.
        Normalize the following raw user-submitted ingredient string into our standard catalog format.
        Raw Input: '{raw_input}'
        
        Rules:
        1. Strip out localized brand names or package specific phrasing unless critical to the commodity.
        2. Map localized terms (e.g., 'Atta', 'Maida') to universal equivalents ('wheat_flour', 'all_purpose_flour').
        """
        response= self.client.models.generate_content(
            model= self.model_name,
            contents= prompt,
            config= types.GenerateContentConfig(
                response_mime_type= "application/json",
                response_schema= NormalizedProduct,
                temperature= 0.1,
            )
        )
        if response.text:
            data= json.loads(response.text)
            return NormalizedProduct(**data)

        return NormalizedProduct(
            canonical_id= "unknown",
            canonical_name= raw_input,
            category= "Other",
            confidence_score= 0.0
        )

    async def normalize(self, raw_input: str) -> NormalizedProduct:
        """Asynchronous execution wrapper to protect server thread concurrency."""
        return await asyncio.to_thread(self._normalize_sync, raw_input)

normalizer_agent= NormalizerAgent()