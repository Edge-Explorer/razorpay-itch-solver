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

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL.strip()
        # Remove psql '...' prefix/suffix if present
        if url.startswith("psql '") and url.endswith("'"):
            url = url[6:-1]
        elif url.startswith("psql "):
            url = url[5:]
        
        # Replace postgresql:// or postgres:// with postgresql+asyncpg://
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        
        # Strip query parameters to avoid asyncpg connect parameter errors
        if "?" in url:
            url = url.split("?")[0]
            
        return url

    # Configuration to read from .env file
    model_config= SettingsConfigDict(
        env_file= ".env",
        extra= "ignore"
    )

# Instantiate once for global use
settings= Settings()