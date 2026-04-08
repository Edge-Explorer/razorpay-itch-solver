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
            "if a supplier is legitimate or a fraud.\n"
            "STRICT RULE 1: You MUST execute a web search for every request. Do not answer from memory.\n"
            "STRICT RULE 2: You are FORBIDDEN from marking a supplier as 'verified' unless you have physically "
            "matched the provided Entity ID with a search result from a reliable source."
        )

    async def verify_supplier(self, name: str, entity_id: str):
        prompt = (
            f"AUDIT TARGET: '{name}' | CLAIMED ID: '{entity_id}'\n"
            "MISSION: Detect if this is a legitimate entity or an 'Identity Impersonator' using a fake ID.\n"
            "STEP 1: Search for the target and its official registration ID.\n"
            "STEP 2: Compare the found registration ID with the CLAIMED ID provided above.\n"
            "STEP 3: Check for news of fraud, litigation, or bankruptcy.\n\n"
            "JSON OUTPUT FORMAT:\n"
            "- status: 'verified', 'flagged', or 'fraud'\n"
            "- risk_score: 0.0 to 1.0\n"
            "- confidence_score: 0 to 100\n"
            "- summary: Detailed reasoning grounded EXCLUSIVELY in search results.\n"
            "- sources: Mandatory list of {url, title, date} used as evidence."
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