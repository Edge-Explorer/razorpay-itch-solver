from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App General Settings
    APP_NAME: str= "BatchProcure AI Aggregator"
    DEBUG: bool= True
    LOG_LEVEL: str= "INFO"

    # Infrastructure
    DATABASE_URL: str= Field(..., env="DATABASE_URL")
    REDIS_URL: str= Field("redis://localhost:6379/0", env= "REDIS_URL")

    # AI & Search Keys
    GEMINI_API_KEY: str= Field(..., env= "GEMINI_API_KEY")
    TAVILY_API_KEY: str= Field(..., env= "TAVILY_API_KEY")

    # Task Queue Settings
    CELERY_BROKER_URL: str= Field("redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str= Field("redis://localhost:6379/0")

    # Configuration to read from .env file
    model_config= SettingsConfigDict(
        env_file= ".env",
        extra= "ignore"
    )

# Instantiate once for global use
settings= Settings()