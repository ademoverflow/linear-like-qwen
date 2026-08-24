"""Teams router (thin): create and list Teams."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.team import Team
from core.models.user import User
from core.services import teams as teams_service

router = APIRouter(prefix="/teams", tags=["Teams"])


class TeamCreateRequest(BaseModel):
    """Body for ``POST /teams``."""

    name: str = Field(min_length=1, max_length=100)
    key: str = Field(min_length=2, max_length=5)
    description: str | None = Field(default=None, max_length=255)


class TeamResponse(BaseModel):
    """A Team as exposed by the API."""

    id: uuid.UUID
    name: str
    key: str
    description: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TeamMemberResponse(BaseModel):
    """A Team member as exposed by the API (ticket 03 assignee picker)."""

    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    role: str


class TeamStateResponse(BaseModel):
    """A Workflow State as exposed by the API (board columns; ADR 0011)."""

    id: uuid.UUID
    name: str
    category: str
    color: str
    position: int


def team_response(team: Team) -> TeamResponse:
    """Build a TeamResponse from a Team."""
    return TeamResponse(
        id=team.id,
        name=team.name,
        key=team.key,
        description=team.description,
        archived_at=team.archived_at,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamResponse:
    """Create a Team (Admin only); seeds the default Workflow and owner."""
    team = await teams_service.create_team(
        session,
        user=user,
        name=payload.name,
        key=payload.key,
        description=payload.description,
    )
    return team_response(team)


@router.get("")
async def list_teams(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamResponse]:
    """List the Teams visible to the current user (admin: all, else own)."""
    teams = await teams_service.list_teams(session, user=user)
    return [team_response(team) for team in teams]


@router.get("/{team_id}/states")
async def list_team_states(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamStateResponse]:
    """List a Team's Workflow States in position order (Team member or Admin)."""
    states = await teams_service.list_team_states(session, user=user, team_id=team_id)
    return [
        TeamStateResponse(
            id=state.id,
            name=state.name,
            category=state.category,
            color=state.color,
            position=state.position,
        )
        for state in states
    ]


@router.get("/{team_id}/members")
async def list_team_members(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamMemberResponse]:
    """List a Team's members with their roles (Team member or Admin)."""
    members = await teams_service.list_team_members(session, user=user, team_id=team_id)
    return [
        TeamMemberResponse(
            id=member.id,
            display_name=member.display_name or member.email,
            avatar_url=member.avatar_url,
            role=role.value,
        )
        for member, role in members
    ]
