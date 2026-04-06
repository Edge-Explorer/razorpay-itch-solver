import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from src.config.settings import settings
from src.models.supplier import Base

config= context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata= Base.metadata

def do_run_migrations(connection):
    """ The actual migration runner (synchronous part) """
    context.configure(connection= connection, target_metadata= target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """ 
    Run migrations in 'online' mode using an Asynchronous Engine 
    """
    configuration= config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"]= settings.DATABASE_URL

    connectable= async_engine_from_config(
        configuration,
        prefix= "sqlalchemy.",
        poolclass= pool.NullPool, 
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    url= settings.DATABASE_URL
    context.configure(url= url, target_metadata= target_metadata, literal_binds= True)
    with context.begin_transaction():
        context.run_migrations()

else:
    asyncio.run(run_migrations_online())