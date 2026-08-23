from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from core.models.serializer import deserialize, serialize
from core.settings import get_settings

settings = get_settings()
async_db_url = settings.database_url.replace("postgresql", "postgresql+asyncpg")

engine = create_async_engine(async_db_url, json_serializer=serialize, json_deserializer=deserialize)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get a session.

    ``expire_on_commit=False`` so services can return ORM objects after
    committing (attributes stay loaded instead of lazy-loading outside the
    request's greenlet).
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
