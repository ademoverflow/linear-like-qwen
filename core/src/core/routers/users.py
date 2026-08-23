"""Users router (thin): list, deactivate/reactivate, promote/demote (brief §5.3)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.user import User
from core.services import users as users_service

router = APIRouter(prefix="/users", tags=["Users"])


class UserResponse(BaseModel):
    """A User as exposed by the API (never the password)."""

    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime


def user_response(user: User) -> UserResponse:
    """Build a UserResponse from a User."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.get("")
async def list_users(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserResponse]:
    """List every User (active and deactivated); Admin only."""
    users = await users_service.list_users(session, user=user)
    return [user_response(u) for u in users]


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: uuid.UUID,
) -> UserResponse:
    """Deactivate a User (422 for the last active Admin); Admin only."""
    updated = await users_service.set_user_active(
        session, user=user, target_id=user_id, active=False
    )
    return user_response(updated)


@router.post("/{user_id}/reactivate")
async def reactivate_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: uuid.UUID,
) -> UserResponse:
    """Reactivate a deactivated User; Admin only."""
    updated = await users_service.set_user_active(
        session, user=user, target_id=user_id, active=True
    )
    return user_response(updated)


@router.post("/{user_id}/promote")
async def promote_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: uuid.UUID,
) -> UserResponse:
    """Promote a User to workspace Admin; Admin only."""
    updated = await users_service.set_user_admin(
        session, user=user, target_id=user_id, is_admin=True
    )
    return user_response(updated)


@router.post("/{user_id}/demote")
async def demote_user(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: uuid.UUID,
) -> UserResponse:
    """Demote a workspace Admin (422 for the last active Admin); Admin only."""
    updated = await users_service.set_user_admin(
        session, user=user, target_id=user_id, is_admin=False
    )
    return user_response(updated)
