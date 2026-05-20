import pytest
from unittest.mock import AsyncMock, patch
from src.agents.normalizer import NormalizerAgent, NormalizedProduct
from src.agents.qa_analyzer import QAAgent, DisputeAnalysis

@pytest.mark.asyncio
async def test_normalizer_agent_success():
    """
    Test that the NormalizerAgent correctly formats raw user input
    into structured Pydantic models.
    """
    # 1. Setup mock response from Gemini Client
    mock_response= AsyncMock()
    mock_response.text= '{"canonical_id": "wheat_flour", "canonical_name": "Whole Wheat Flour", "category": "Grains", "confidence_score": 0.95}'
    agent= NormalizerAgent()
    
    # 2. Patch the generate_content API call
    with patch.object(agent.client.models, 'generate_content', return_value= mock_response):
        result= await agent.normalize("Chakki Atta Premium Bag")
        
        # 3. Assertions
        assert isinstance(result, NormalizedProduct)
        assert result.canonical_id== "wheat_flour"
        assert result.canonical_name== "Whole Wheat Flour"
        assert result.confidence_score== 0.95
        
@pytest.mark.asyncio
async def test_qa_agent_dispute_resolution():
    """
    Test that the QA Agent accurately classifies dispute reports
    and maps them to structured analysis results.
    """
    mock_response= AsyncMock()
    mock_response.text= '{"suggested_status": "logistics_fault", "suggested_severity": "medium", "confidence_score": 0.88, "reasoning": "Damaged in transit"}'
    agent= QAAgent()
    
    with patch.object(agent.client.models, 'generate_content', return_value=mock_response):
        result = await agent.triage_dispute(
            description="The sacks arrived wet and torn.",
            pickup_notes="All dry and loaded safely.",
            dropoff_notes="Left outside in heavy rain."
        )
        
        assert isinstance(result, DisputeAnalysis)
        assert result.suggested_status == "logistics_fault"
        assert result.suggested_severity == "medium"
        assert result.confidence_score == 0.88