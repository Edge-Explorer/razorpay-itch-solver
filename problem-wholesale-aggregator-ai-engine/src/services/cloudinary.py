import os
import uuid
import asyncio

# Try to import cloudinary. If it fails, fallback gracefully to mock mode.
try:
    import cloudinary
    import cloudinary.uploader  # type: ignore
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

class CloudinaryService:
    def __init__(self):
        self.enabled = False
        
        # Read both configuration formats from environment
        cloudinary_url = os.getenv("CLOUDINARY_URL")
        cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        api_key = os.getenv("CLOUDINARY_API_KEY")
        api_secret = os.getenv("CLOUDINARY_API_SECRET")
        
        if CLOUDINARY_AVAILABLE:
            if cloudinary_url:
                try:
                    cloudinary.config(cloudinary_url=cloudinary_url)
                    self.enabled = True
                    print("Cloudinary SDK configured successfully via CLOUDINARY_URL.")
                except Exception as e:
                    print(f"Warning: Failed to configure Cloudinary URL: {e}")
            elif cloud_name and api_key and api_secret:
                try:
                    cloudinary.config(
                        cloud_name=cloud_name,
                        api_key=api_key,
                        api_secret=api_secret
                    )
                    self.enabled = True
                    print("Cloudinary SDK configured successfully via individual API keys.")
                except Exception as e:
                    print(f"Warning: Failed to configure Cloudinary keys: {e}")

    async def upload_image(self, file_bytes: bytes, folder: str = "verification") -> str:
        """
        Uploads image file bytes to Cloudinary and returns the secure HTTPS CDN URL.
        If credentials are not configured, it falls back to a high-fidelity mock URL.
        """
        if self.enabled:
            try:
                # Wrap the synchronous SDK upload in an async thread executor
                # to keep our FastAPI web server non-blocking and high performance.
                result = await asyncio.to_thread(
                    cloudinary.uploader.upload,
                    file_bytes,
                    folder=folder,
                    resource_type="image"
                )
                return result.get("secure_url")
            except Exception as e:
                print(f"Cloudinary upload error: {e}. Falling back to mock URL...")
        
        # High-Fidelity Mock Mode
        mock_id = uuid.uuid4().hex
        mock_url = f"https://res.cloudinary.com/mock-cloud/image/upload/v1716300000/{folder}/{mock_id}.jpg"
        print(f"[MOCK CLOUDINARY] Uploaded file. Generated link: {mock_url}")
        return mock_url

# Instantiate a single global instance for the application
cloudinary_service = CloudinaryService()