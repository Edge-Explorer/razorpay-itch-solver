import os
import uuid
import asyncio

try:
    import cloudinary
    import cloudinary.uploader  # type: ignore
    CLOUDINARY_AVAILABLE= True
except ImportError:
    CLOUDINARY_AVAILABLE= False

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