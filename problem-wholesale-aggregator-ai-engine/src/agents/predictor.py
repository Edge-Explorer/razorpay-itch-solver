from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config.settings import settings
from src.agents.tools import research_area_density
import asyncio
import json

class SpeedPrediction(BaseModel):
    """Schema for the AI's reasoning about aggregation velocity."""
    estimated_hours_to_lock: int= Field(description= "Estimate of hours until MOQ is met")
    confidence_level: str= Field(description= "Low, Medium or High based on data density")
    reasoning: str= Field(description= "Brief explanation of why this estimate was made")

class PredictorAgent:
    """
    AI Agent that predicts how long it will take for a pool to reach MOQ
    by analyzing real-world restaurant density data.
    """
    def __init__(self) -> None:
        self.client= genai.Client(api_key= settings.GEMINI_API_KEY)
        self.model_name= "gemini-2.0-flash"

    async def predict_aggregation_speed(self, zip_code: str, product_name: str) -> SpeedPrediction:
        # 1. Fetch real-world data using our Tavily tool
        area_data= await research_area_density(zip_code)

        # 2. Construct the reasoning prompt
        prompt= f"""
        You are a logistics analyst for a wholesale food aggregator.
        Based on the following research data about restaurants in ZIP code {zip_code}, 
        predict how fast we can aggregate a wholesale order for '{product_name}'.
        
        Research Data: {area_data}
        
        Rules:
        1. If density is high (>20 restaurants), predict a fast lock (2-6 hours).
        2. If density is low, predict a longer lock (12-24 hours).
        3. Provide clear reasoning.
        """

        # 3. Call Gemini to reason about the data
        response= await asyncio.to_thread(
            self.client.models.generate_content,
            model= self.model_name,
            contents= prompt,
            config= types.GenerateContentConfig(
                response_mime_type= "application/json",
                response_schema= SpeedPrediction,
                temperature= 0.2 
            )
        )
        if response.text:
            return SpeedPrediction(**json.loads(response.text))

        return SpeedPrediction(
            estimated_hours_to_lock= 24,
            confidence_level= "Low",
            reasoning= "Fallback due to insufficient area data."
        )

predictor_agent= PredictorAgent()