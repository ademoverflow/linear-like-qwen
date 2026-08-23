"""User middlewares."""

import uuid
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import engine
from core.models.user import User
from core.settings import get_settings

settings = get_settings()

# Optional bearer token from Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    access_token: Annotated[str | None, Cookie()] = None,
    bearer_token: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Get the current user from the token.

    Supports both:
    - Cookie-based auth (webapp)
    - Bearer token in Authorization header (mobile app)

    The auth read uses its own short-lived session: the endpoint's
    transactional session must stay untouched so services can open it with
    ``session.begin()`` (FastAPI caches dependency values by callable, so a
    shared ``get_session`` would leak the auth read's open transaction).

    Args:
        access_token: The token from cookie.
        bearer_token: The token from Authorization header.

    Returns:
        The current user (detached; all attributes loaded).

    Raises:
        HTTPException: If the token is invalid or the user is not found.

    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Try bearer token first (mobile app), then fall back to cookie (webapp)
    token = bearer_token.credentials if bearer_token else access_token

    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(
            token,
            settings.core_jwt_secret_key,
            algorithms=[settings.core_jwt_algorithm],
        )
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        try:
            user_id = uuid.UUID(str(subject))
        except ValueError:
            raise credentials_exception from None
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise credentials_exception from None

    async with AsyncSession(engine, expire_on_commit=False) as auth_session:
        user = (
            await auth_session.exec(select(User).where(User.id == user_id).limit(1))
        ).one_or_none()

        if user is None:
            raise credentials_exception

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Load every attribute before the session closes and detaches the
        # instance; the returned user is used after teardown.
        await auth_session.refresh(user)

    return user
