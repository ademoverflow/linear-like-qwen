"""Moment Core health router."""

from fastapi import APIRouter
from pydantic import BaseModel

from core import __version__
from core.misc import get_uptime

health_router = APIRouter()


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    uptime: float
    version: str


@health_router.get("/health", tags=["Health"])
def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", uptime=get_uptime(), version=__version__)
