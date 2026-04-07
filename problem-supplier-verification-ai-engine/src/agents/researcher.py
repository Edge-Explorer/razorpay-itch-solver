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
            f"Research the supplier '{name}' with Entity ID '{entity_id}'. "
            "Verify their registration and search for any red flags or news. "
            "Return a final JSON report with: 'status', 'risk_score' (0 to 1), "
            "and a 'summary'."
        )

        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config={
                "tools": Tools,
                "system_instruction": self.system_instruction,
            }
        )
        
        return response.text