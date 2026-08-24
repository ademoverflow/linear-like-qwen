from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core import __version__
from core.domain.errors import DomainError
from core.routers import (
    auth_router,
    health_router,
    invitations_router,
    issues_router,
    labels_router,
    teams_router,
    users_router,
)
from core.settings import get_settings

settings = get_settings()

API_PREFIX = "/api/v1"


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
    title="Linear Like Qwen",
    description="Linear Like Qwen Core API",
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


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    """Map DomainError subclasses to the API error envelope."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


# Health stays unversioned so load balancers and compose healthchecks keep working.
app.include_router(health_router)

# Every resource router is mounted here. Add: api_router.include_router(<name>_router)
api_router = APIRouter(prefix=API_PREFIX)
api_router.include_router(auth_router)
api_router.include_router(teams_router)
api_router.include_router(issues_router)
api_router.include_router(labels_router)
api_router.include_router(invitations_router)
api_router.include_router(users_router)
app.include_router(api_router)
