import pytest   # type: ignore
import json
from fastapi.testclient import TestClient  # type: ignore
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.main import app
from src.services.db import get_session
from src.agents.verifier import DocumentVerificationResult
from src.agents.normalizer import NormalizedProduct
from src.models.suppliers import VerificationStatus

#Initialize TestClient
client= TestClient(app)

@pytest.fixture
def mock_db_session():
    """Fixture to mock the database session for FastAPI dependencies."""
    db= AsyncMock()
    # Mock commit, refresh, flush, add
    db.commit= AsyncMock()
    db.refresh= AsyncMock()
    db.add= MagicMock()
    return db
def test_supplier_registration_success(mock_db_session):
    """
    Tests that a supplier can register successfully, documents are uploaded
    to Cloudinary, and Gemini OCR verifies matching details.
    """
    # 1. Override the database session dependency
    app.dependency_overrides[get_session]= lambda: mock_db_session
    
    # 2. Setup mock return values for Cloudinary and Gemini Verifier
    mock_pan_result= DocumentVerificationResult(
        is_authentic= True,
        fields_match= True,
        extracted_name= "Fresh Agro",
        extracted_number= "ABCDE1234F",
        reasoning= "PAN details match expected inputes for Fresh Agro."
    )
    mock_aadhar_result= DocumentVerificationResult(
        is_authentic= True,
        fields_match= True,
        extracted_name= "Fresh Agro",
        extracted_number= "123456789012",
        reasoning= "Aadhar details match expected inputes for Fresh Agro."
    )
    
    # Mock files to send
    files= {
        "pan_image": ("pan.jpg", b"fake_pan_image_bytes", "image/jpeg"),
        "aadhar_image": ("aadhar.jpg", b"fake_aadhar_image_bytes", "image/jpeg")
    }
    data= {
        "name": "Fresh Agro",
        "contact_email": "fresh@agro.com",
        "pan_number": "ABCDE1234F",
        "aadhar_number": "123456789012"
    }
    
    # Patch Cloudinary upload and Gemini Verifier agent calls
    with patch("src.api.router.cloudinary_service.upload_image", new_callable= AsyncMock) as mock_upload, \
        patch("src.api.router.document_verifier_agent.verify_document", new_callable= AsyncMock) as mock_verify:
            
            mock_upload.side_effect= [
                "https://res.cloudinary.com/demo/pan.jpg",
                "https://res.cloudinary.com/demo/aadhar.jpg"
            ]
            mock_verify.side_effect= [mock_pan_result, mock_aadhar_result]
            
            # Send request 
            response= client.post("/api/v1/suppliers/register", data= data, files= files)
            
            # Assertions
            assert response.status_code== 200
            res_json= response.json()
            assert res_json["status"]== "processed"
            assert res_json["verification_status"]== "verified"
            assert res_json["is_verified"] is True
            assert "Fresh Agro" in res_json["audit_notes"]
            assert res_json["cloudinary_urls"]["pan_url"]== "https://res.cloudinary.com/demo/pan.jpg"
            
            # Check database interactions
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
    app.dependency_overrides.clear()
    
def test_supplier_registration_rejected(mock_db_session):
    """
    Tests that registration is rejected if Gemini OCR reports mismatching details.
    """
    app.dependency_overrides[get_session]= lambda: mock_db_session
    
    mock_pan_result= DocumentVerificationResult(
        is_authentic= True,
        fields_match= False,
        extracted_name= "Different Name Ltd",
        extracted_number= "ABCDE1234F",
        reasoning= "Name on PAN does not match expected name Fresh Agro."
    )
    mock_aadhar_result= DocumentVerificationResult(
        is_authentic= True,
        fields_match= True,
        extracted_name= "Fresh Agro",
        extracted_number= "123456789012",
        reasoning= "Aadhar matches expected inputes."
    )
    files= {
        "pan_image": ("pan.jpg", b"fake_pan_bytes", "image/jpeg"),
        "aadhar_image": ("aadhar.jpg", b"fake_aadhar_bytes", "image/jpeg")
    }
    data= {
        "name": "Fresh Agro",
        "contact_email": "fresh@agro.com",
        "pan_number": "ABCDE1234F",
        "aadhar_number": 123456789012
    }
    with patch("src.api.router.cloudinary_service.upload_image", new_callable= AsyncMock) as mock_upload, \
        patch("src.api.router.document_verifier_agent.verify_document", new_callable= AsyncMock) as mock_verify:
            mock_upload.side_effect= [
                "https://res.cloudinary.com/demo/pan.jpg",
                "https://res.cloudinary.com/demo/aadhar.jpg"
            ]
            mock_verify.side_effect=[mock_pan_result, mock_aadhar_result]
            response= client.post("/api/v1/suppliers/register", data= data, files= files)
            
            assert response.status_code==200
            res_json= response.json()
            assert res_json["verification_status"]== "rejected"
            assert res_json["is_verified"] is False
            assert "Name on PAN does not match" in res_json["audit_notes"]
    app.dependency_overrides.clear()
    
@pytest.mark.asyncio
async def test_redis_normalization_caching():
    """
    Verifies that calling the Normalization logic twice with the same raw name
    hits Redis on the second call and bypasses the Gemini Normalizer Agent.
    """
    # Create mock NormalizedProduct
    mock_normalized= NormalizedProduct(
        canonical_id= "wheat_flour",
        canonical_name= "Whole Wheat Flour",
        category= "Grains",
        confidence_score= 0.98
    )
    # 1. Setup mock redis_service and normalizer_agent
    mock_redis= AsyncMock()
    mock_redis.get.return_value= None
    mock_redis.set= AsyncMock()
    
    mock_agent= AsyncMock()
    mock_agent.normalize.return_value= mock_normalized
    
    # 2. Patch services inside src.api.router
    with patch("src.api.router.redis_service", mock_redis), \
         patch("src.api.router.normalizer_agent", mock_agent), \
         patch("src.api.router.get_session", lambda: AsyncMock()), \
         patch("src.api.router.distributed_lock", lambda *args, **kwargs: AsyncMock()):
                # Simulating first call (Cache Miss)
                raw_name= "Chakki Atta Premium"
                raw_name_key= raw_name.lower().strip()
                cache_key= f"normalized_product:{raw_name_key}"
                
                # First lookup:
                cached_val= await mock_redis.get(cache_key)
                if not cached_val:
                    normalized= await mock_agent.normalize(raw_name)
                    await mock_redis.set(cache_key, normalized.model_dump(), ex= 604800) # Cache for 7 days
                
                # Assert agent was called and Redis set was executed
                mock_agent.normalize.assert_called_once_with(raw_name)
                mock_redis.set.assert_called_once()
                
                # Reset mock calls for second run
                mock_agent.normalize.reset_mock()
                mock_redis.set.reset_mock()
                
                # Simulating second call (Cache Hit)
                mock_redis.get.return_value= json.dumps(mock_normalized.model_dump())
                cached_val= await mock_redis.get(cache_key)
                
                if cached_val:
                    normalized= NormalizedProduct(**json.loads(cached_val))
                    
                # Assert agent was NOT called
                mock_agent.normalize.assert_not_called()
                assert normalized.canonical_id== "wheat_flour"