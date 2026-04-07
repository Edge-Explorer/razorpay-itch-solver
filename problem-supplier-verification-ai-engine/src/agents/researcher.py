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
            f"You are investigating '{name}' (Entity ID: {entity_id}).\n"
            "STEP 1: Use your tools to find their registration and latest news.\n"
            "STEP 2: Analyze all results for fraud, red flags, or bankruptcies.\n"
            "STEP 3: Compare your findings with the provided Entity ID.\n\n"
            "FINAL REQUIREMENT: Output your result as a JSON OBJECT containing:\n"
            "- status: 'verified', 'flagged', or 'fraud'\n"
            "- risk_score: 0.0 to 1.0\n"
            "- confidence_score: 0 to 100\n"
            "- summary: A detailed analysis (min 3 sentences)\n"
            "- sources: List of {url, title, date} used for your verdict."
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