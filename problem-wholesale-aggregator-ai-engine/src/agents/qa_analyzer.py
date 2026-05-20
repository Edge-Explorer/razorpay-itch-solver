from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from src.config.settings import settings
from src.models.disputes import DisputeStatus, DisputeSeverity
import asyncio
import json

class DisputeAnalysis(BaseModel):
    """Schema for the AI QA Agent's triaging decision."""
    suggested_status: str= Field(
        description= "Must be one of: resolved_in_favor_of_buyer, resolved_in_favor_of_supplier, logistics_fault"
    )
    suggested_severity: str= Field(
        description= "Must be one of: low, medium, high"
    )
    confidence_score: float= Field(
        description= "Confidence score between 0.0 and 1.0"
    )
    reasoning: str= Field(
        description= "Detailed logical explanation comparing the supplier, driver, and restaurant claims."
    )

class QAAgent:
    """
    AI Agent that automatically triages disputes by analyzing descriptions 
    and determining if liability lies with the Supplier, Buyer, or Transporter.
    """
    def __init__(self) -> None:
        self.client= genai.Client(api_key= settings.GEMINI_API_KEY)
        self.model_name= "gemini-2.0-flash"
    
    def _triage_sync(self, description: str, pickup_notes: str, dropoff_notes: str) -> DisputeAnalysis:
        prompt= f"""
        You are an expert arbitrator for a B2B agricultural marketplace. 
        Triage the following dispute between a Restaurant (Buyer), a Wholesaler (Supplier), and a Driver (Transporter).
        
        Dispute Description (Restaurant): '{description}'
        Pickup Notes (Supplier/Driver at warehouse): '{pickup_notes}'
        Dropoff Notes (Driver/Restaurant at delivery): '{dropoff_notes}'
        
        Rules:
        1. If the items were in perfect condition at pickup but arrived damaged, class it as 'logistics_fault'.
        2. If the packaging is intact but the product quality inside is bad (e.g., rotten, fungus, bugs), class it as 'resolved_in_favor_of_buyer' (Supplier Fault).
        3. If the restaurant claims damage but both pickup and dropoff notes verify perfect delivery, class it as 'resolved_in_favor_of_supplier' (suspicion of Buyer fraud).
        """
        response= self.client.models.generate_content(
            model= self.model_name,
            contents= prompt,
            config= types.GenerateContentConfig(
                response_mime_type= "application/json",
                response_schema= DisputeAnalysis,
                temperature= 0.1
            )
        )
        if response.text:
            return DisputeAnalysis(**json.loads(response.text))
        
        return DisputeAnalysis(
            suggested_status= "resolved_in_favor_of_supplier",
            suggested_severity= "low",
            confidence_score= 0.0,
            reasoning= "Fallback: AI failed to parse text."
        )
        
    async def triage_dispute(self, description: str, pickup_notes: str, dropoff_notes: str) -> DisputeAnalysis:
        """Asynchronously wraps the synchronous triaging logic."""
        return await asyncio.to_thread(self._triage_sync, description, pickup_notes, dropoff_notes)

qa_agent= QAAgent()