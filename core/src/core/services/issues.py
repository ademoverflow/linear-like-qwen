"""Issue use-cases (brief §3): creation, detail, editing, Activity listing."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import literal_column
from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Actor, IssueResource, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.identifiers import format_identifier
from core.domain.issues import (
    validate_description,
    validate_estimate,
    validate_priority,
    validate_title,
)
from core.domain.workflow import (
    Category,
    WorkflowStateRule,
    select_default_state,
    transition,
)
from core.models.activity import Activity
from core.models.issue import Issue
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.services.activity import record_activity
from core.services.actors import load_actor

ACTIVITY_ISSUE_CREATED = "issue.created"
ACTIVITY_ISSUE_UPDATED = "issue.updated"
ACTIVITY_ISSUE_STATE_CHANGED = "issue.state_changed"

MSG_TEAM_NOT_FOUND = "Team not found"
MSG_TEAM_ARCHIVED = "Team is archived"
MSG_ISSUE_NOT_FOUND = "Issue not found"
MSG_STALE_UPDATE = "The Issue was updated by someone else. Reload and try again."
MSG_ASSIGNEE_NOT_MEMBER = "Assignee must be a member of the Issue's Team"
MSG_PARENT_INVALID = "Parent must be a non-archived Issue of the same Team, one level deep"
MSG_PARENT_IS_SELF = "An Issue cannot be its own parent"
MSG_TITLE_REQUIRED = "Title is required"
MSG_STATE_NOT_IN_TEAM = "State does not belong to the Issue's Team"

# Canonical edit order: the Activity rows of one update follow this sequence.
EDITABLE_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "priority",
    "assignee_id",
    "parent_id",
    "due_date",
    "estimate",
)


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
    title = validate_title(title)

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
        await session.refresh(issue, ["state", "created_at", "updated_at"])
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


async def get_issue(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID
) -> tuple[Team, Issue, Issue | None]:
    """Fetch an Issue's detail (with its parent) for the acting user.

    Args:
        session: The database session.
        user: The authenticated acting user (Team member or Admin).
        issue_id: The Issue to fetch.

    Returns:
        The Team, the Issue (State/assignee eager-loaded) and its parent
        (or ``None`` when the Issue has none).

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor (non-members get 404, not 403).

    """
    actor = await load_actor(session, user)
    issue = await _visible_issue(session, actor=actor, issue_id=issue_id)
    team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
    parent: Issue | None = None
    if issue.parent_id is not None:
        parent = (
            await session.exec(select(Issue).where(Issue.id == issue.parent_id))
        ).one_or_none()
    return team, issue, parent


async def update_issue(
    session: AsyncSession,
    *,
    user: User,
    issue_id: uuid.UUID,
    updated_at: datetime,
    changes: dict[str, Any],
) -> tuple[Team, Issue]:
    """Edit an Issue's fields with optimistic concurrency (brief §3.3, ADR 0008).

    The caller must echo the ``updated_at`` they last saw; a mismatch is a
    409. Every changed field emits exactly one ``issue.updated`` Activity
    row with human-readable from/to values. ``number``, ``creator_id`` and
    ``team_id`` are never touched.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team member or Admin).
        issue_id: The Issue to edit.
        updated_at: The ``updated_at`` the client last saw.
        changes: Field name to new value, only for the fields the client
            sent (``None`` clears a nullable field).

    Returns:
        The Team and the updated Issue (with its State loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor.
        ConflictError: If ``updated_at`` is stale.
        ValidationError: If a new value is invalid (assignee not a Team
            member, parent not one level deep, ...).

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        if issue.updated_at != updated_at:
            raise ConflictError(MSG_STALE_UPDATE)

        team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
        for field in EDITABLE_FIELDS:
            if field in changes:
                await _apply_change(
                    session,
                    issue=issue,
                    team=team,
                    actor_id=actor.user_id,
                    change=_FieldChange(field=field, value=changes[field]),
                )
        await session.flush()
        await session.refresh(issue, ["state", "assignee", "created_at", "updated_at"])
        return team, issue


async def transition_issue(
    session: AsyncSession,
    *,
    user: User,
    issue_id: uuid.UUID,
    state_id: uuid.UUID,
    updated_at: datetime,
) -> tuple[Team, Issue]:
    """Move an Issue to a new State (brief §3.3, §4.2).

    The single code path for State changes: the generic ``update_issue``
    cannot touch ``state_id``. The caller must echo the last-seen
    ``updated_at``; a mismatch is a 409 (ADR 0008). Entering a completed or
    canceled State stamps the matching timestamp and clears the other; any
    other target clears both (``core.domain.workflow.transition``). Every
    transition emits one ``issue.state_changed`` Activity row with the
    from/to State names. Moving a State to itself is a no-op (no Activity,
    no timestamp change).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team member or Admin).
        issue_id: The Issue to transition.
        state_id: The target State (must belong to the Issue's Team).
        updated_at: The ``updated_at`` the client last saw.

    Returns:
        The Team and the updated Issue (with its State loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor (non-members get 404, not 403).
        ForbiddenError: If the Issue's Team is archived.
        ConflictError: If ``updated_at`` is stale.
        ValidationError: If the target State does not belong to the
            Issue's Team's Workflow.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        if issue.updated_at != updated_at:
            raise ConflictError(MSG_STALE_UPDATE)

        team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)

        workflow = (await session.exec(select(Workflow).where(Workflow.team_id == team.id))).one()
        state = (
            await session.exec(
                select(WorkflowState).where(
                    WorkflowState.id == state_id,
                    WorkflowState.workflow_id == workflow.id,
                )
            )
        ).one_or_none()
        if state is None:
            raise ValidationError(MSG_STATE_NOT_IN_TEAM)

        if issue.state_id == state.id:
            return team, issue

        current_state = (
            await session.exec(select(WorkflowState).where(WorkflowState.id == issue.state_id))
        ).one()
        effect = transition(_to_rule(state), datetime.now(UTC))
        issue.state_id = state.id
        issue.completed_at = effect.completed_at
        issue.canceled_at = effect.canceled_at
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_ISSUE_STATE_CHANGED,
                field="state_id",
                from_value=current_state.name,
                to_value=state.name,
            ),
        )
        await session.flush()
        await session.refresh(issue, ["state", "assignee", "created_at", "updated_at"])
        return team, issue


@dataclass(frozen=True)
class _FieldChange:
    """A single Issue field change (name plus raw client value)."""

    field: str
    value: object


async def _apply_change(
    session: AsyncSession,
    *,
    issue: Issue,
    team: Team,
    actor_id: uuid.UUID,
    change: _FieldChange,
) -> None:
    """Validate one field change and write its Activity row when it differs."""
    field, value = change.field, change.value
    current = getattr(issue, field)
    new_value: object
    from_display: object
    to_display: object

    if field == "title":
        if value is None:
            raise ValidationError(MSG_TITLE_REQUIRED)
        new_value = validate_title(cast("str", value))
        from_display = current
        to_display = new_value
    elif field == "description":
        new_value = validate_description(cast("str | None", value))
        from_display = current
        to_display = new_value
    elif field == "priority":
        new_value = validate_priority(cast("str", value))
        from_display = current
        to_display = new_value
    elif field == "estimate":
        new_value = validate_estimate(cast("int | None", value))
        from_display = str(current) if current is not None else None
        to_display = str(new_value) if new_value is not None else None
    elif field == "due_date":
        new_value = value
        from_display = cast("date", current).isoformat() if current is not None else None
        to_display = cast("date", value).isoformat() if value is not None else None
    elif field == "assignee_id":
        new_value = value
        from_display = issue.assignee.display_name if issue.assignee else None
        to_display = None
        if new_value is not None:
            assignee = await _ensure_assignee_member(session, issue, cast("uuid.UUID", new_value))
            to_display = assignee.display_name
    elif field == "parent_id":
        new_value = value
        from_display = await _parent_identifier(session, current, team.key)
        to_display = None
        if new_value is not None:
            parent = await _ensure_parent(session, issue, cast("uuid.UUID", new_value))
            to_display = format_identifier(team.key, parent.number)
    else:
        return

    if new_value == current:
        return
    setattr(issue, field, new_value)
    record_activity(
        session,
        Activity(
            issue_id=issue.id,
            actor_id=actor_id,
            kind=ACTIVITY_ISSUE_UPDATED,
            field=field,
            from_value=cast("str | None", from_display),
            to_value=cast("str | None", to_display),
        ),
    )


async def _visible_issue(
    session: AsyncSession,
    *,
    actor: Actor,
    issue_id: uuid.UUID,
    for_update: bool = False,
) -> Issue:
    """Load an Issue the actor may see (non-members get 404, not 403).

    Archived Issues are invisible. ``for_update`` locks the row
    (``SELECT ... FOR UPDATE``) for the write path.

    Args:
        session: The database session.
        actor: The acting user (id, admin flag, team roles).
        issue_id: The Issue to load.
        for_update: Whether to lock the row for writing.

    Returns:
        The Issue (State/assignee eager-loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor.

    """
    query = (
        select(Issue)
        .where(Issue.id == issue_id)
        .options(
            joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
        )
    )
    if for_update:
        query = query.with_for_update(of=Issue)
    issue = (await session.exec(query)).one_or_none()
    if issue is None or not can(actor, Action.ISSUE_VIEW, IssueResource(issue.team_id)):
        raise NotFoundError(MSG_ISSUE_NOT_FOUND)
    if issue.archived_at is not None:
        raise NotFoundError(MSG_ISSUE_NOT_FOUND)
    return issue


async def _ensure_assignee_member(session: AsyncSession, issue: Issue, user_id: uuid.UUID) -> User:
    """Load the assignee candidate; it must be a member of the Issue's Team."""
    user = (await session.exec(select(User).where(User.id == user_id))).one_or_none()
    if user is None:
        raise ValidationError(MSG_ASSIGNEE_NOT_MEMBER)
    membership = (
        await session.exec(
            select(Membership).where(
                Membership.user_id == user_id, Membership.team_id == issue.team_id
            )
        )
    ).one_or_none()
    if membership is None:
        raise ValidationError(MSG_ASSIGNEE_NOT_MEMBER)
    return user


async def _ensure_parent(session: AsyncSession, issue: Issue, parent_id: uuid.UUID) -> Issue:
    """Load the parent candidate; same Team, one level deep, not archived."""
    if parent_id == issue.id:
        raise ValidationError(MSG_PARENT_IS_SELF)
    parent = (await session.exec(select(Issue).where(Issue.id == parent_id))).one_or_none()
    if (
        parent is None
        or parent.team_id != issue.team_id
        or parent.archived_at is not None
        or parent.parent_id is not None
    ):
        raise ValidationError(MSG_PARENT_INVALID)
    return parent


async def _parent_identifier(
    session: AsyncSession, parent_id: uuid.UUID | None, team_key: str
) -> str | None:
    """Return the identifier of the current parent (``None`` when unset)."""
    if parent_id is None:
        return None
    parent = (await session.exec(select(Issue).where(Issue.id == parent_id))).one_or_none()
    return format_identifier(team_key, parent.number) if parent else None


async def list_issue_activity(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID
) -> list[Activity]:
    """List an Issue's Activity rows, oldest first (ticket 03).

    Args:
        session: The database session.
        user: The authenticated acting user (Team member or Admin).
        issue_id: The Issue to list Activity for.

    Returns:
        The Issue's Activity rows in chronological order (oldest first),
        with the actor eager-loaded.

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor.

    """
    actor = await load_actor(session, user)
    issue = await _visible_issue(session, actor=actor, issue_id=issue_id)
    activities = (
        await session.exec(
            select(Activity)
            .where(Activity.issue_id == issue.id)
            .options(joinedload(Activity.actor))  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            .order_by(literal_column("seq"))  # insertion order (migration c0de8a243260)
        )
    ).all()
    return list(activities)
