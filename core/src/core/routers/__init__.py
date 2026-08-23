from .auth import router as auth_router
from .health import health_router
from .issues import router as issues_router
from .teams import router as teams_router

__all__ = [
    "auth_router",
    "health_router",
    "issues_router",
    "teams_router",
]
