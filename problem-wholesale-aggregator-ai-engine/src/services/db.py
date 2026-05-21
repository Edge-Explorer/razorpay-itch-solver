from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config.settings import settings
from typing import AsyncGenerator

# Create the Async Engine
engine= create_async_engine(
    settings.async_database_url,
    echo= settings.DEBUG, # allows us to see the SQL queries in the console during development
    future= True,
    pool_pre_ping= True,
    connect_args={"ssl": True}
)

# Create a Session Factory
AsyncSessionLocal= async_sessionmaker(
    bind= engine,
    class_= AsyncSession,
    expire_on_commit= False,
    autoflush= False,
)

# FastAPI Dependency
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Context manager session alias for background workers
async_session = AsyncSessionLocal