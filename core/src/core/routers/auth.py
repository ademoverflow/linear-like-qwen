"""Auth router (thin): bootstrap/invited register, login, logout, me, status."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.user import User
from core.services import auth as auth_service
from core.settings import get_settings

router = APIRouter(prefix="/auth", tags=["Auth"])
settings = get_settings()


class RegisterRequest(BaseModel):
    """Body for ``POST /auth/register``."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Invitation token (required once bootstrap is closed; ADR 0012).
    token: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    """Body for ``POST /auth/login``."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class MembershipResponse(BaseModel):
    """A team membership as exposed by ``GET /auth/me``."""

    team_id: uuid.UUID
    team_key: str
    team_name: str
    role: str


class MeResponse(BaseModel):
    """The ``me`` payload (never contains the token body)."""

    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime
    memberships: list[MembershipResponse]


class RegistrationStatusResponse(BaseModel):
    """Whether bootstrap registration is open (user base still empty)."""

    bootstrap_open: bool


def me_response(user: User, memberships: list[auth_service.MembershipInfo]) -> MeResponse:
    """Build the ``me`` payload from the user and their memberships."""
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        memberships=[
            MembershipResponse(
                team_id=m.team_id, team_key=m.team_key, team_name=m.team_name, role=m.role
            )
            for m in memberships
        ],
    )


def set_auth_cookie(response: Response, token: str) -> None:
    """Set the HttpOnly ``access_token`` cookie (flags per Settings, ADR 0002)."""
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=settings.core_jwt_expiration_timedelta_minutes * 60,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        httponly=True,
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    """Register: bootstrap Admin while the user base is empty, else closed."""
    user = await auth_service.register(
        session, email=payload.email, password=payload.password, token=payload.token
    )
    memberships = await auth_service.get_me(session, user)
    return me_response(user, memberships)


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    """Log in: verify, rate-limit, set the cookie, return the me payload."""
    client_ip = request.client.host if request.client else "unknown"
    user, token = await auth_service.login(
        session, email=payload.email, password=payload.password, client_ip=client_ip
    )
    set_auth_cookie(response, token)
    memberships = await auth_service.get_me(session, user)
    return me_response(user, memberships)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Log out: clear the access-token cookie."""
    response.delete_cookie(key="access_token", domain=settings.cookie_domain or None, path="/")


@router.get("/me")
async def me(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeResponse:
    """Return the current user's profile, admin flag and team memberships."""
    memberships = await auth_service.get_me(session, user)
    return me_response(user, memberships)


@router.get("/status")
async def registration_status(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegistrationStatusResponse:
    """Public: whether bootstrap registration is open."""
    return RegistrationStatusResponse(
        bootstrap_open=await auth_service.registration_status(session)
    )
