from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import __version__
from core.routers import health_router
from core.settings import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator:
    """Lifespan of the application.

    Args:
        app (FastAPI): FastAPI application instance.

    Returns:
        AsyncIterator: Async context manager for lifespan.

    """
    config = Config("core/src/core/alembic/alembic.ini")
    command.upgrade(config, "head")
    yield


app = FastAPI(
    title="Ademoverflow Template",
    description="Ademoverflow Template Core API",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.webapp_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
