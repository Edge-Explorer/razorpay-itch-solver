import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Hardened Configuration Model for the Supplier Verification Engine.
    Enforces validation for all environment variables before the app starts.
    """

    # --- Project Info ---
    PROJECT_NAME: str= "Supplier Verification AI Engine"
    ENVIRONMENT: Literal["development", "staging", "production"]= "development"
    LOG_LEVEL: str= "INFO"

    # --- AI & LLM (Gemini 2.0 Flash) ---
    GOOGLE_API_KEY: str

    # --- Infrastructure (Backend & Persistence) ---
    REDIS_URL: str= "redis://localhost:6379/0"
    DATABASE_URL: str= "postgresql+asyncpg://user:password@localhost:5432/supplier_db"

    # --- Scaling & Performance Tuning ---
    MAX_RETRIES: int= 3
    RESEARCH_TIMEOUT: int= 60

    # Pydantic Settings Configuration
    # This automatically reads your .env file and maps it to the variables above.
    model_config= SettingsConfigDict(
        env_file= ".env",
        env_file_encoding= "utf-8",
        case_sensitive= True
    )

# Singleton instance to be used across the API, Workers, and Agents.
settings= Settings()