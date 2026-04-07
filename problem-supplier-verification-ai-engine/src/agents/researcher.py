from google import genai
from src.config.settings import settings
from src.agents.tools import Tools
import json

class ResearcherAgent:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        self.model_id = "gemini-2.0-flash"
        
        self.system_instruction = (
            "You are a Senior Trust & Safety Researcher. Your goal is to verify "
            "if a supplier is legitimate or a fraud. You must use your tools "
            "to search the web and verify entity registration numbers."
        )

    async def verify_supplier(self, name: str, entity_id: str):
        prompt = (
            f"AUDIT PLAN for supplier '{name}' (ID: {entity_id}):\n"
            "1. Search for official registration and news.\n"
            "2. Compare the Registry data vs the Web data.\n"
            "3. FOR EVERY RED FLAG: Mention the Source URL and Date.\n"
            "4. Return ONLY a JSON with: status, risk_score (0-1), confidence_score (0-100), "
            "summary, and an array of 'sources' (url, title, date)."
        )

        # Gemini will automatically call the synchronous tools in Tools list
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "tools": Tools,
                "system_instruction": self.system_instruction,
            }
        )
        
        return response.text