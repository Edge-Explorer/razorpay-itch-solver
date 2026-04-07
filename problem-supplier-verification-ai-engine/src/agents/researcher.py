import google.generativeai as genai
from src.config.settings import settings
from src.agents.tools import Tools
import json

genai.configure(api_key= settings.GOOGLE_API_KEY)

class ResearcherAgent:
    """
    A Pro-level Auditor Agent using Gemini 2.0 Flash with Function Calling.
    Designed for deep research and risk assessment.
    """
    def __init__(self):
        self.system_prompt= (
            "You are a Senior Trust & Safety Researcher. Your goal is to verify "
            "if a supplier is legitimate or a fraud. You must use your tools "
            "to search the web and verify entity registration numbers."
        )

        self.model= genai.GenerativeModel(
            model_name= "gemini-2.0-flash",
            tools= Tools,
            system_instruction= self.system_prompt
        )

        self.session = self.model.start_chat(enable_automatic_function_calling=True)

    async def verify_supplier(self, name: str, entity_id: str):
        """ Performs the automated reasoning loop to research a supplier """
        prompt= (
            f"Research the supplier '{name}' with Entity ID '{entity_id}'. "
            "Verify their registration and search for any red flags or news. "
            "Return a final JSON report with: 'status', 'risk_score' (0 to 1), "
            "and a 'summary'."
        )

        response= self.session.send_message(prompt)

        return response.text