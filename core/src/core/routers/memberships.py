"""Members router (thin): Team member management (ticket 08, brief §5.2/§9)."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.domain.authz import Role
from core.middlewares.user import get_current_user
from core.models.user import User
from core.services import memberships as memberships_service
from core.services import teams as teams_service

router = APIRouter(prefix="/teams/{team_id}", tags=["Members"])


class TeamMemberResponse(BaseModel):
    """A Team member as exposed by the API (ticket 03 assignee picker)."""

    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    role: str


class TeamMemberCandidateResponse(BaseModel):
    """A User who can be added to the Team (the add picker, ticket 08)."""

    id: uuid.UUID
    display_name: str
    email: str
    avatar_url: str | None


class MemberAddRequest(BaseModel):
    """Body for ``POST /teams/{team_id}/members``."""

    user_id: uuid.UUID


class MemberRoleRequest(BaseModel):
    """Body for ``PATCH /teams/{team_id}/members/{user_id}``."""

    role: Literal["owner", "member"]


def member_response(user: User, role: Role) -> TeamMemberResponse:
    """Build a TeamMemberResponse from a User and their role."""
    return TeamMemberResponse(
        id=user.id,
        display_name=user.display_name or user.email,
        avatar_url=user.avatar_url,
        role=role.value,
    )


@router.get("/members")
async def list_team_members(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamMemberResponse]:
    """List a Team's members with their roles (Team member or Admin)."""
    members = await teams_service.list_team_members(session, user=user, team_id=team_id)
    return [member_response(member, role) for member, role in members]


@router.get("/member-candidates")
async def list_member_candidates(
    team_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TeamMemberCandidateResponse]:
    """List the active Users who are not yet members (Team owner or Admin)."""
    candidates = await memberships_service.list_member_candidates(
        session, user=user, team_id=team_id
    )
    return [
        TeamMemberCandidateResponse(
            id=candidate.id,
            display_name=candidate.display_name or candidate.email,
            email=candidate.email,
            avatar_url=candidate.avatar_url,
        )
        for candidate in candidates
    ]


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: uuid.UUID,
    payload: MemberAddRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamMemberResponse:
    """Add an existing User to the Team as a member (Team owner or Admin)."""
    membership = await memberships_service.add_team_member(
        session, user=user, team_id=team_id, user_id=payload.user_id
    )
    target = await memberships_service.get_member_user(session, membership.user_id)
    return member_response(target, Role(membership.role))


@router.patch("/members/{user_id}")
async def update_team_member_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRoleRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamMemberResponse:
    """Change a member's role (Team owner or Admin)."""
    membership = await memberships_service.update_team_member_role(
        session,
        user=user,
        team_id=team_id,
        user_id=user_id,
        role=Role(payload.role),
    )
    target = await memberships_service.get_member_user(session, membership.user_id)
    return member_response(target, Role(membership.role))


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Remove a member from the Team (Team owner or Admin)."""
    await memberships_service.remove_team_member(
        session, user=user, team_id=team_id, user_id=user_id
    )
