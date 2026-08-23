"""Invitations router (thin): invite by email, list (ADR 0012)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.invitation import Invitation
from core.models.user import User
from core.services import invitations as invitations_service

router = APIRouter(prefix="/invitations", tags=["Invitations"])


class InvitationCreateRequest(BaseModel):
    """Body for ``POST /invitations``."""

    email: EmailStr


class InvitationResponse(BaseModel):
    """An Invitation as exposed by the API (the token is never revealed)."""

    id: uuid.UUID
    email: str
    invited_by: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class InvitationCreatedResponse(InvitationResponse):
    """The invite response: includes the raw token, shown exactly once."""

    token: str


def invitation_response(invitation: Invitation) -> InvitationResponse:
    """Build an InvitationResponse from an Invitation."""
    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        invited_by=invitation.invited_by,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def invite(
    payload: InvitationCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvitationCreatedResponse:
    """Invite a User by email; re-inviting replaces the previous token."""
    invitation, token = await invitations_service.invite_user(
        session, user=user, email=payload.email
    )
    return InvitationCreatedResponse(
        id=invitation.id,
        email=invitation.email,
        invited_by=invitation.invited_by,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        created_at=invitation.created_at,
        token=token,
    )


@router.get("")
async def list_invitations(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[InvitationResponse]:
    """List all Invitations (pending, expired, accepted); Admin only."""
    invitations = await invitations_service.list_invitations(session, user=user)
    return [invitation_response(invitation) for invitation in invitations]
