from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from core.models.serializer import deserialize, serialize
from core.settings import get_settings

settings = get_settings()
async_db_url = settings.database_url.replace("postgresql", "postgresql+asyncpg")

engine = create_async_engine(async_db_url, json_serializer=serialize, json_deserializer=deserialize)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get a session."""
    async with AsyncSession(engine) as session:
        yield session
