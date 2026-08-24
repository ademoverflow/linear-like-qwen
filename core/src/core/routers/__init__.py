from .auth import router as auth_router
from .comments import router as comments_router
from .health import health_router
from .invitations import router as invitations_router
from .issues import router as issues_router
from .labels import router as labels_router
from .teams import router as teams_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "comments_router",
    "health_router",
    "invitations_router",
    "issues_router",
    "labels_router",
    "teams_router",
    "users_router",
]
