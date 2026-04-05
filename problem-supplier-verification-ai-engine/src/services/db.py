from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.config.settings import settings

# For 1k-10k scale, we use 'pool_size' and 'max_overflow' to handle spikes.
engine= create_async_engine(
    settings.DATABASE_URL,
    echo= settings.ENVIRONMENT == "development",
    pool_size= 20,
    max_overflow= 10
)

# The Session Factory: Generates isolated sessions for every user request
AsyncSessionLocal= async_sessionmaker(
    bind= engine,
    class_= AsyncSession,
    expire_on_commit= False # Essential for high-concurrency async apps
)

# Connection Provider: A 'Generator' used by FastAPI
async def get_db():
    """ 
    Pro-Developer Dependency Injection.
    Ensures every request gets a clean connection that is safely closed afterwards.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()