"""Issues router (thin): create and list Issues."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.domain.identifiers import format_identifier
from core.middlewares.user import get_current_user
from core.models.issue import Issue
from core.models.user import User
from core.services import issues as issues_service

router = APIRouter(prefix="/issues", tags=["Issues"])


class IssueCreateRequest(BaseModel):
    """Body for ``POST /issues``."""

    team_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)


class IssueResponse(BaseModel):
    """An Issue as exposed by the API (identifier computed, never stored)."""

    id: uuid.UUID
    team_id: uuid.UUID
    number: int
    identifier: str
    title: str
    description: str | None
    state_id: uuid.UUID
    state_name: str
    state_category: str
    state_color: str
    priority: str
    assignee_id: uuid.UUID | None
    assignee_display_name: str | None
    assignee_avatar_url: str | None
    creator_id: uuid.UUID
    parent_id: uuid.UUID | None
    due_date: date | None
    estimate: int | None
    completed_at: datetime | None
    canceled_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


def issue_response(issue: Issue, team_key: str) -> IssueResponse:
    """Build an IssueResponse from an Issue (State/assignee eager-loaded)."""
    return IssueResponse(
        id=issue.id,
        team_id=issue.team_id,
        number=issue.number,
        identifier=format_identifier(team_key, issue.number),
        title=issue.title,
        description=issue.description,
        state_id=issue.state.id,
        state_name=issue.state.name,
        state_category=issue.state.category,
        state_color=issue.state.color,
        priority=issue.priority,
        assignee_id=issue.assignee.id if issue.assignee else None,
        assignee_display_name=issue.assignee.display_name if issue.assignee else None,
        assignee_avatar_url=issue.assignee.avatar_url if issue.assignee else None,
        creator_id=issue.creator_id,
        parent_id=issue.parent_id,
        due_date=issue.due_date,
        estimate=issue.estimate,
        completed_at=issue.completed_at,
        canceled_at=issue.canceled_at,
        archived_at=issue.archived_at,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_issue(
    payload: IssueCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueResponse:
    """Create an Issue (Team member or Admin); allocates the next number."""
    team, issue = await issues_service.create_issue(
        session, user=user, team_id=payload.team_id, title=payload.title
    )
    return issue_response(issue, team.key)


@router.get("")
async def list_issues(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    team_id: Annotated[uuid.UUID, Query()],
) -> list[IssueResponse]:
    """List a Team's non-archived Issues, newest number first."""
    team, issues = await issues_service.list_issues(session, user=user, team_id=team_id)
    return [issue_response(issue, team.key) for issue in issues]
