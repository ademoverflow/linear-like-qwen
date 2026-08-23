"""Issue use-cases (brief §3): creation with number allocation, listing."""

import uuid
from typing import cast

from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, TeamResource, can
from core.domain.errors import ForbiddenError, NotFoundError, ValidationError
from core.domain.workflow import Category, WorkflowStateRule, select_default_state
from core.models.activity import Activity
from core.models.issue import Issue
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.services.activity import record_activity
from core.services.actors import load_actor

ACTIVITY_ISSUE_CREATED = "issue.created"

MSG_TITLE_INVALID = "Title must be 1-255 characters"
MSG_TEAM_NOT_FOUND = "Team not found"
MSG_TEAM_ARCHIVED = "Team is archived"
TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 255


def _to_rule(state: WorkflowState) -> WorkflowStateRule:
    """Map an ORM WorkflowState to the plain domain record."""
    return WorkflowStateRule(
        name=state.name,
        category=cast("Category", state.category),
        color=state.color,
        position=state.position,
    )


async def create_issue(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, title: str
) -> tuple[Team, Issue]:
    """Create an Issue in a Team (brief §3.2).

    The per-Team number is allocated from ``teams.next_issue_number`` while
    the Team row is locked (``SELECT ... FOR UPDATE``) inside the same
    transaction, so concurrent creates never yield duplicate numbers (ADR
    0010). The Issue starts in the Team's default State (first backlog, else
    first unstarted) and an ``issue.created`` Activity row is written.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team member or Admin).
        team_id: The Team the Issue belongs to.
        title: The Issue title (1-255 chars, trimmed).

    Returns:
        The Team and the created Issue (with its State loaded).

    Raises:
        ValidationError: If the title is invalid.
        NotFoundError: If the Team does not exist or is not visible to the
            actor (non-members get 404, not 403).
        ForbiddenError: If the Team is archived.

    """
    title = title.strip()
    if not TITLE_MIN_LENGTH <= len(title) <= TITLE_MAX_LENGTH:
        raise ValidationError(MSG_TITLE_INVALID)

    async with session.begin():
        actor = await load_actor(session, user)
        team = (
            await session.exec(select(Team).where(Team.id == team_id).with_for_update())
        ).one_or_none()
        if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
            raise NotFoundError(MSG_TEAM_NOT_FOUND)
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)

        workflow = (await session.exec(select(Workflow).where(Workflow.team_id == team.id))).one()
        states = list(
            await session.exec(
                select(WorkflowState)
                .where(WorkflowState.workflow_id == workflow.id)
                .order_by(WorkflowState.position)  # type: ignore[attr-defined,arg-type]
            )
        )
        default_rule = select_default_state([_to_rule(s) for s in states])
        default_state = next(s for s in states if s.name == default_rule.name)

        number = team.next_issue_number
        team.next_issue_number = number + 1
        issue = Issue(
            team_id=team.id,
            number=number,
            title=title,
            state_id=default_state.id,
            creator_id=actor.user_id,
        )
        session.add(issue)
        await session.flush()
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_ISSUE_CREATED,
            ),
        )
        await session.refresh(issue, ["state"])
        return team, issue


async def list_issues(
    session: AsyncSession, *, user: User, team_id: uuid.UUID
) -> tuple[Team, list[Issue]]:
    """List a Team's non-archived Issues, newest number first.

    Args:
        session: The database session.
        user: The authenticated acting user.
        team_id: The Team to list Issues for.

    Returns:
        The Team and its Issues (State and assignee eager-loaded).

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor.

    """
    actor = await load_actor(session, user)
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    issues = (
        await session.exec(
            select(Issue)
            .where(
                Issue.team_id == team.id,
                Issue.archived_at.is_(None),  # type: ignore[union-attr]
            )
            .options(
                joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
                joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            )
            .order_by(Issue.number.desc())  # type: ignore[attr-defined]
        )
    ).all()
    return team, list(issues)
