from google import genai
from src.config.settings import settings
from typing import Sequence
import asyncio

class EmbeddingService:
    """
    Service responsible for generating semantic vector embeddings using Gemini
    to power fuzzy similarity matching for product catalogs.
    """
    def __init__(self) -> None:
        # Initialize the official google-genai client
        self.client= genai.Client(api_key= settings.GEMINI_API_KEY)
        # Using Google's dedicated multi-lingual embedding model
        self.model_name= "text-embedding-004"
    
    def _generate_sync(self, text: str) -> list[float]:
        """Synchronous call to Google GenAI SDK."""
        response= self.client.models.embed_content(
            model= self.model_name,
            contents= text,
        )
        # Extract the float values from the returned embedding object
        return list(response.embeddings[0].values)

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Asynchronously generates an embedding by offloading the synchronous
        SDK call to a separate thread, preventing event loop blocking.
        """
        return await asyncio.to_thread(self._generate_sync, text)

embedding_service= EmbeddingService()