"""Issues router (thin): create, list, detail, edit and Activity for Issues."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

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


class IssueDetailResponse(IssueResponse):
    """Issue detail with the parent's identifier and title (ticket 03)."""

    parent_identifier: str | None
    parent_title: str | None


class IssueUpdateRequest(BaseModel):
    """Body for ``PATCH /issues/{id}`` (ADR 0008: echo the last-seen ``updated_at``)."""

    updated_at: datetime
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    priority: Literal["none", "urgent", "high", "medium", "low"] | None = None
    assignee_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    due_date: date | None = None
    estimate: int | None = Field(default=None, ge=0, le=21)


class IssueTransitionRequest(BaseModel):
    """Body for ``POST /issues/{id}/transitions`` (ADR 0008: echo the last-seen ``updated_at``)."""

    state_id: uuid.UUID
    updated_at: datetime


class ActivityResponse(BaseModel):
    """An Activity row as exposed by the API (from/to are display-ready text)."""

    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_display_name: str | None
    kind: str
    field: str | None
    from_value: str | None
    to_value: str | None
    created_at: datetime


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


def issue_detail_response(issue: Issue, team_key: str, parent: Issue | None) -> IssueDetailResponse:
    """Build an IssueDetailResponse (State/assignee eager-loaded)."""
    base = issue_response(issue, team_key).model_dump()
    return IssueDetailResponse(
        **base,
        parent_identifier=format_identifier(team_key, parent.number) if parent else None,
        parent_title=parent.title if parent else None,
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


@router.get("/{issue_id}")
async def get_issue(
    issue_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueDetailResponse:
    """Fetch an Issue's detail (Team member or Admin; non-members get 404)."""
    team, issue, parent = await issues_service.get_issue(session, user=user, issue_id=issue_id)
    return issue_detail_response(issue, team.key, parent)


@router.patch("/{issue_id}")
async def update_issue(
    issue_id: uuid.UUID,
    payload: IssueUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueResponse:
    """Edit an Issue's fields; replies 409 when the echoed ``updated_at`` is stale."""
    changes = {
        name: getattr(payload, name)
        for name in payload.model_fields_set
        if name in issues_service.EDITABLE_FIELDS
    }
    team, issue = await issues_service.update_issue(
        session,
        user=user,
        issue_id=issue_id,
        updated_at=payload.updated_at,
        changes=changes,
    )
    return issue_response(issue, team.key)


@router.post("/{issue_id}/transitions")
async def transition_issue(
    issue_id: uuid.UUID,
    payload: IssueTransitionRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IssueResponse:
    """Move an Issue to a new State (Team member or Admin); 409 when stale."""
    team, issue = await issues_service.transition_issue(
        session,
        user=user,
        issue_id=issue_id,
        state_id=payload.state_id,
        updated_at=payload.updated_at,
    )
    return issue_response(issue, team.key)


@router.get("/{issue_id}/activity")
async def list_issue_activity(
    issue_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ActivityResponse]:
    """List the Issue's Activity rows, oldest first (Team member or Admin)."""
    activities = await issues_service.list_issue_activity(session, user=user, issue_id=issue_id)
    return [
        ActivityResponse(
            id=activity.id,
            actor_id=activity.actor_id,
            actor_display_name=activity.actor.display_name if activity.actor else None,
            kind=activity.kind,
            field=activity.field,
            from_value=activity.from_value,
            to_value=activity.to_value,
            created_at=activity.created_at,
        )
        for activity in activities
    ]
