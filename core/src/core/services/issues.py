"""Issue use-cases (brief §3-§4): create, list, edit, transition, Activity and bulk."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import and_, case, delete, literal_column, or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql.elements import Case, ColumnElement
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from core.domain.authz import Action, Actor, IssueResource, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.identifiers import format_identifier
from core.domain.issues import (
    BulkAction,
    confirm_identifier,
    validate_description,
    validate_estimate,
    validate_priority,
    validate_title,
)
from core.domain.listing import (
    PRIORITY_RANK,
    Cursor,
    CursorIssue,
    IssueQuery,
    SortSpec,
    cursor_sort_value,
    encode_cursor,
    validate_cursor_for_sort,
)
from core.domain.workflow import (
    Category,
    WorkflowStateRule,
    select_default_state,
    transition,
)
from core.models.activity import Activity
from core.models.comment import Comment
from core.models.issue import Issue
from core.models.issue_label import IssueLabel
from core.models.label import Label
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
    "label_ids",
)

# Attributes refreshed after every write so the echoed ``updated_at`` (and the
# eager-loaded relationships) are the real server values, not naive defaults.
REFRESH_ATTRIBUTES: list[str] = ["state", "assignee", "labels", "created_at", "updated_at"]

MSG_ARCHIVE_FORBIDDEN = "Only a Team owner or an Admin can archive an Issue"
MSG_DELETE_ADMIN_ONLY = "Only an Admin can hard-delete an Issue"
MSG_NOT_ARCHIVED = "The Issue is not archived"
MSG_BULK_ISSUES_NOT_FOUND = "Some Issues could not be found"
MSG_BULK_SAME_TEAM = "Issues must belong to the same Team"
MSG_BULK_ARCHIVED = "Some Issues are archived"
MSG_ARCHIVE_OWNER_ONLY = "Only a Team owner can archive Issues"
MSG_LABELS_NOT_IN_TEAM = "Labels must belong to the Issue's Team"


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
        await session.refresh(issue, REFRESH_ATTRIBUTES)
        return team, issue


async def list_issues(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, query: IssueQuery
) -> tuple[Team, list[Issue], str | None]:
    """List a Team's Issues with filters, sort and pagination.

    Archived Issues are hidden by default; ``include_archived`` lists
    them alongside the active ones (brief §3.4, ticket 07). Filters
    (``state_id``/``assignee_id``/``label_id``/``priority``,
    combinable), sort (``created``/``updated``/``priority`` with
    ``asc``/``desc``, default ``created:desc``) and keyset (cursor)
    pagination (default page 50, max 200) per brief §9.

    Args:
        session: The database session.
        user: The authenticated acting user.
        team_id: The Team to list Issues for.
        query: The parsed, validated list request.

    Returns:
        The Team, the page of Issues (State/assignee/labels eager-loaded)
        and the cursor for the next page (``None`` when there is none).

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor (non-members get 404, not 403).

    """
    actor = await load_actor(session, user)
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if team.archived_at is not None:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if query.cursor is not None:
        validate_cursor_for_sort(query.cursor, query.sort)
    statement = (
        select(Issue)
        .where(Issue.team_id == team.id)
        .options(
            joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            selectinload(Issue.labels),  # type: ignore[arg-type,attr-defined]  # M2M: selectinload avoids row duplication
        )
    )
    if not query.include_archived:
        statement = statement.where(Issue.archived_at.is_(None))  # type: ignore[union-attr]  # SQLModel field is a Column at runtime
    if query.state_ids:
        statement = statement.where(Issue.state_id.in_(query.state_ids))  # type: ignore[attr-defined]
    if query.assignee_ids:
        statement = statement.where(Issue.assignee_id.in_(query.assignee_ids))  # type: ignore[union-attr]
    if query.priorities:
        statement = statement.where(Issue.priority.in_(query.priorities))  # type: ignore[attr-defined]
    if query.label_ids:
        # EXISTS over the M2M: an Issue matches when any of its Labels is in
        # the filter set (Labels are always same-Team by construction).
        statement = statement.where(
            Issue.labels.any(Label.id.in_(query.label_ids))  # type: ignore[attr-defined]
        )
    statement = _apply_sort(statement, query.sort)
    if query.cursor is not None:
        statement = statement.where(_cursor_predicate(query.sort, query.cursor))
    statement = statement.limit(query.limit + 1)
    rows = list((await session.exec(statement)).all())
    has_more = len(rows) > query.limit
    page = rows[: query.limit]
    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        value = cursor_sort_value(
            query.sort, CursorIssue(last.created_at, last.updated_at, last.priority)
        )
        next_cursor = encode_cursor(query.sort, value, last.number, last.id)
    return team, page, next_cursor


def _apply_sort(statement: SelectOfScalar[Issue], sort: SortSpec) -> SelectOfScalar[Issue]:
    """Order a list statement per the sort (tie-breaker: number desc)."""
    if sort.key == "created":
        ordered = statement.order_by(
            Issue.created_at.desc() if sort.direction == "desc" else Issue.created_at.asc(),  # type: ignore[attr-defined]
            Issue.number.desc(),  # type: ignore[attr-defined]
        )
    elif sort.key == "updated":
        ordered = statement.order_by(
            Issue.updated_at.desc() if sort.direction == "desc" else Issue.updated_at.asc(),  # type: ignore[attr-defined]
            Issue.number.desc(),  # type: ignore[attr-defined]
        )
    else:
        rank = _priority_rank_expr()
        ordered = statement.order_by(
            rank.desc() if sort.direction == "desc" else rank.asc(),
            Issue.number.desc(),  # type: ignore[attr-defined]
        )
    return ordered


def _priority_rank_expr() -> Case:
    """Return a SQL expression ranking priorities (urgent highest, none lowest)."""
    return case(
        (Issue.priority == "urgent", PRIORITY_RANK["urgent"]),  # type: ignore[arg-type]
        (Issue.priority == "high", PRIORITY_RANK["high"]),  # type: ignore[arg-type]
        (Issue.priority == "medium", PRIORITY_RANK["medium"]),  # type: ignore[arg-type]
        (Issue.priority == "low", PRIORITY_RANK["low"]),  # type: ignore[arg-type]
        else_=PRIORITY_RANK["none"],
    )


def _cursor_predicate(sort: SortSpec, cursor: Cursor) -> ColumnElement[bool]:
    """Keyset predicate: strictly after the cursor's row in sort order."""
    if sort.key in ("created", "updated"):
        column = Issue.created_at if sort.key == "created" else Issue.updated_at
        timestamp = datetime.fromisoformat(str(cursor.value))
        if sort.direction == "desc":
            return or_(
                column < timestamp,  # type: ignore[arg-type]
                and_(column == timestamp, Issue.number < cursor.number),  # type: ignore[arg-type]
            )
        return or_(
            column > timestamp,  # type: ignore[arg-type]
            and_(column == timestamp, Issue.number < cursor.number),  # type: ignore[arg-type]
        )
    rank = _priority_rank_expr()
    if sort.direction == "desc":
        return or_(
            rank < cursor.value,
            and_(rank == cursor.value, Issue.number < cursor.number),  # type: ignore[arg-type]
        )
    return or_(
        rank > cursor.value,
        and_(rank == cursor.value, Issue.number < cursor.number),  # type: ignore[arg-type]
    )


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
    if team.archived_at is not None:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
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
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        for field in EDITABLE_FIELDS:
            if field not in changes:
                continue
            if field == "label_ids":
                # Not an Issue column: full-set Label replace with per-label
                # Activity rows (ticket 05).
                await _apply_label_change(
                    session,
                    issue=issue,
                    actor_id=actor.user_id,
                    label_ids=cast("list[uuid.UUID]", changes[field]),
                )
                continue
            await _apply_change(
                session,
                issue=issue,
                team=team,
                actor_id=actor.user_id,
                change=_FieldChange(field=field, value=changes[field]),
            )
        await session.flush()
        await session.refresh(issue, REFRESH_ATTRIBUTES)
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
        await session.refresh(issue, REFRESH_ATTRIBUTES)
        return team, issue


async def archive_issue(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID
) -> tuple[Team, Issue]:
    """Archive an Issue (soft delete, brief §3.4).

    Sets ``archived_at`` on the Issue and, per brief §3.4, on every
    non-archived child Issue (the hierarchy is one level deep); already
    archived children are skipped. One ``issue.updated`` Activity row
    (``field="archived_at"``, the timestamp as ``to_value``) per archived
    Issue, matching the bulk archive (ticket 05).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        issue_id: The Issue to archive.

    Returns:
        The Team and the archived Issue (with its State loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is already archived,
            or is not visible to the actor (non-members get 404).
        ForbiddenError: If the Team is archived, or the actor is not a
            Team owner (or Admin).

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        if not can(actor, Action.ISSUE_ARCHIVE, TeamResource(team.id)):
            raise ForbiddenError(MSG_ARCHIVE_FORBIDDEN)
        now = datetime.now(UTC)
        issue.archived_at = now
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="archived_at",
                to_value=now.isoformat(),
            ),
        )
        children = list(
            (
                await session.exec(
                    select(Issue).where(Issue.parent_id == issue.id).with_for_update(of=Issue)
                )
            ).all()
        )
        for child in children:
            if child.archived_at is not None:
                continue
            child.archived_at = now
            record_activity(
                session,
                Activity(
                    issue_id=child.id,
                    actor_id=actor.user_id,
                    kind=ACTIVITY_ISSUE_UPDATED,
                    field="archived_at",
                    to_value=now.isoformat(),
                ),
            )
        await session.flush()
        await session.refresh(issue, REFRESH_ATTRIBUTES)
        return team, issue


async def restore_issue(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID
) -> tuple[Team, Issue]:
    """Restore an archived Issue (brief §3.4).

    Clears ``archived_at`` on the Issue only: restoring a parent does not
    restore its children (brief §3.4). Emits one ``issue.updated``
    Activity row (``field="archived_at"``, the old timestamp as
    ``from_value``).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        issue_id: The archived Issue to restore.

    Returns:
        The Team and the restored Issue (with its State loaded).

    Raises:
        NotFoundError: If the Issue does not exist or is not visible to
            the actor (non-members get 404).
        ForbiddenError: If the Team is archived, or the actor is not a
            Team owner (or Admin).
        ValidationError: If the Issue is not archived.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(
            session, actor=actor, issue_id=issue_id, for_update=True, include_archived=True
        )
        if issue.archived_at is None:
            raise ValidationError(MSG_NOT_ARCHIVED)
        team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        if not can(actor, Action.ISSUE_RESTORE, TeamResource(team.id)):
            raise ForbiddenError(MSG_ARCHIVE_FORBIDDEN)
        previous = issue.archived_at
        issue.archived_at = None
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="archived_at",
                from_value=previous.isoformat(),
            ),
        )
        await session.flush()
        await session.refresh(issue, REFRESH_ATTRIBUTES)
        return team, issue


async def hard_delete_issue(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID, identifier: str
) -> Team:
    """Hard-delete an Issue: Admin only, confirmed by identifier (brief §3.4).

    Permanently removes the Issue and its children (the hierarchy is one
    level deep), cascading to their Comments, Activity rows and Label
    links; no Activity row is written — the trail goes with the Issue.
    Admins may hard-delete even in an archived Team (the Team archive is a
    soft hide; the removal is a workspace-level Admin action).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (must be a workspace Admin).
        issue_id: The Issue to delete.
        identifier: The identifier the client repeated as confirmation.

    Returns:
        The Team (the Issue itself is gone).

    Raises:
        NotFoundError: If the Issue does not exist or is not visible to
            the actor (non-members get 404).
        ForbiddenError: If the actor is not a workspace Admin.
        ValidationError: If the identifier does not match the Issue.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(
            session, actor=actor, issue_id=issue_id, for_update=True, include_archived=True
        )
        if not can(actor, Action.ISSUE_DELETE, None):
            raise ForbiddenError(MSG_DELETE_ADMIN_ONLY)
        team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
        confirm_identifier(format_identifier(team.key, issue.number), identifier)
        children = list(
            (
                await session.exec(
                    select(Issue).where(Issue.parent_id == issue.id).with_for_update(of=Issue)
                )
            ).all()
        )
        for target in [*children, issue]:
            await session.execute(delete(IssueLabel).where(IssueLabel.issue_id == target.id))  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
            await session.execute(delete(Comment).where(Comment.issue_id == target.id))  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
            await session.execute(delete(Activity).where(Activity.issue_id == target.id))  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
            await session.execute(delete(Issue).where(Issue.id == target.id))  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
        await session.flush()
        return team


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
    include_archived: bool = False,
) -> Issue:
    """Load an Issue the actor may see (non-members get 404, not 403).

    Archived Issues are invisible unless ``include_archived`` (the
    restore and hard-delete paths need to reach them). ``for_update``
    locks the row (``SELECT ... FOR UPDATE``) for the write path.

    Args:
        session: The database session.
        actor: The acting user (id, admin flag, team roles).
        issue_id: The Issue to load.
        for_update: Whether to lock the row for writing.
        include_archived: Whether archived Issues are visible to this
            caller (the restore and hard-delete paths).

    Returns:
        The Issue (State/assignee eager-loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is archived (and
            ``include_archived`` is false), or is not visible to the
            actor.

    """
    query = (
        select(Issue)
        .where(Issue.id == issue_id)
        .options(
            joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            selectinload(Issue.labels),  # type: ignore[arg-type,attr-defined]  # M2M: selectinload avoids row duplication
        )
    )
    if for_update:
        query = query.with_for_update(of=Issue)
    issue = (await session.exec(query)).one_or_none()
    if issue is None or not can(actor, Action.ISSUE_VIEW, IssueResource(issue.team_id)):
        raise NotFoundError(MSG_ISSUE_NOT_FOUND)
    if issue.archived_at is not None and not include_archived:
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


async def _apply_label_change(
    session: AsyncSession, *, issue: Issue, actor_id: uuid.UUID, label_ids: list[uuid.UUID]
) -> None:
    """Replace an Issue's Label set (full-set replace, ticket 05).

    Emits exactly one ``issue.updated`` Activity row per added label
    (``to_value`` = name) and per removed label (``from_value`` = name);
    removed rows first, then added, each name-ordered.
    """
    target = await _ensure_labels(session, issue, label_ids)
    target_ids = {label.id for label in target}
    current_ids = {label.id for label in issue.labels}
    removed = sorted(
        (label for label in issue.labels if label.id not in target_ids),
        key=lambda label: label.name,
    )
    added = sorted(
        (label for label in target if label.id not in current_ids), key=lambda label: label.name
    )
    if not removed and not added:
        return
    issue.labels = target
    for label in removed:
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="label_id",
                from_value=label.name,
            ),
        )
    for label in added:
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="label_id",
                to_value=label.name,
            ),
        )


async def _ensure_labels(
    session: AsyncSession, issue: Issue, label_ids: list[uuid.UUID]
) -> list[Label]:
    """Load the target Labels; every id must be a Label of the Issue's Team."""
    if not label_ids:
        return []
    rows = list(
        await session.exec(
            select(Label).where(Label.id.in_(label_ids), Label.team_id == issue.team_id)  # type: ignore[attr-defined]
        )
    )
    if len(rows) != len(set(label_ids)):
        raise ValidationError(MSG_LABELS_NOT_IN_TEAM)
    by_id = {label.id: label for label in rows}
    return [by_id[label_id] for label_id in dict.fromkeys(label_ids)]


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
    team = (await session.exec(select(Team).where(Team.id == issue.team_id))).one()
    if team.archived_at is not None:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    activities = (
        await session.exec(
            select(Activity)
            .where(Activity.issue_id == issue.id)
            .options(joinedload(Activity.actor))  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            .order_by(literal_column("seq"))  # insertion order (migration c0de8a243260)
        )
    ).all()
    return list(activities)


async def bulk_update_issues(
    session: AsyncSession,
    *,
    user: User,
    issue_ids: list[uuid.UUID],
    action: BulkAction,
) -> tuple[Team, list[Issue]]:
    """Apply one bulk action to several Issues of one Team (brief §4.4).

    All-or-nothing in one transaction: every id and value is validated
    before anything is written (one bad id -> 400, nothing changes). The
    ``state_id`` action goes through the domain ``transition()`` (Issues
    already in the target State are skipped); the ``archive`` action is
    owner-only. One Activity row per Issue (per added/removed label for
    label actions). Bulk is unversioned (no ``updated_at`` echo; ADR 0008).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        issue_ids: The Issues to apply the action to (same Team).
        action: The single action to apply (validated in the domain layer).

    Returns:
        The Team and the updated Issues (State/assignee/labels eager-loaded),
        ordered by number.

    Raises:
        NotFoundError: If any Issue's Team is not visible to the actor
            (non-members get 404, not 403).
        ForbiddenError: If the Team is archived, or the actor is not a Team
            owner (or Admin) and the action is archiving.
        ValidationError: If an id is unknown, the Issues span Teams, an
            Issue is archived, or the action's value is invalid.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        unique_ids = list(dict.fromkeys(issue_ids))
        team, issues = await _validate_bulk_targets(session, actor=actor, unique_ids=unique_ids)
        if action.archive and not can(actor, Action.ISSUE_ARCHIVE, TeamResource(team.id)):
            raise ForbiddenError(MSG_ARCHIVE_OWNER_ONLY)
        context = await _build_bulk_context(session, team=team, issues=issues, action=action)
        ordered = sorted(issues, key=lambda item: item.number)
        for issue in ordered:
            await _apply_bulk_action_to_issue(
                session,
                issue=issue,
                actor_id=actor.user_id,
                action=action,
                context=context,
            )
        await session.flush()
        for issue in ordered:
            await session.refresh(issue, REFRESH_ATTRIBUTES)
        return team, ordered


@dataclass(frozen=True)
class _BulkContext:
    """The shared, pre-validated values of one bulk operation."""

    state: WorkflowState | None
    assignee: User | None
    add_labels: list[Label]
    remove_labels: list[Label]
    now: datetime


async def _validate_bulk_targets(
    session: AsyncSession, *, actor: Actor, unique_ids: list[uuid.UUID]
) -> tuple[Team, list[Issue]]:
    """Load and validate the bulk target Issues (row-locked, all-or-nothing).

    Args:
        session: The database session (inside the caller's transaction).
        actor: The acting user.
        unique_ids: The deduplicated Issue ids.

    Returns:
        The shared Team and the locked Issues (State/assignee/labels
        eager-loaded).

    Raises:
        NotFoundError: If any Issue's Team is not visible to the actor
            (non-members get 404, not 403).
        ValidationError: If an id is unknown, the Issues span Teams, or an
            Issue is already archived.
        ForbiddenError: If the Team is archived.

    """
    issues = list(
        (
            await session.exec(
                select(Issue)
                .where(Issue.id.in_(unique_ids))  # type: ignore[attr-defined]
                .options(
                    joinedload(Issue.state),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
                    joinedload(Issue.assignee),  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
                    selectinload(Issue.labels),  # type: ignore[arg-type,attr-defined]  # M2M: selectinload avoids row duplication
                )
                .with_for_update(of=Issue)
            )
        ).all()
    )
    team_ids = {issue.team_id for issue in issues}
    for team_id in team_ids:
        if not can(actor, Action.TEAM_VIEW, TeamResource(team_id)):
            raise NotFoundError(MSG_ISSUE_NOT_FOUND)
    if len(issues) != len(unique_ids):
        raise ValidationError(MSG_BULK_ISSUES_NOT_FOUND)
    if len(team_ids) > 1:
        raise ValidationError(MSG_BULK_SAME_TEAM)
    team = (await session.exec(select(Team).where(Team.id == next(iter(team_ids))))).one()
    if team.archived_at is not None:
        raise ForbiddenError(MSG_TEAM_ARCHIVED)
    if any(issue.archived_at is not None for issue in issues):
        raise ValidationError(MSG_BULK_ARCHIVED)
    return team, issues


async def _build_bulk_context(
    session: AsyncSession, *, team: Team, issues: list[Issue], action: BulkAction
) -> _BulkContext:
    """Validate the bulk action's target values (State, assignee, Labels)."""
    now = datetime.now(UTC)
    state = (
        await _ensure_state_in_team(session, team, action.state_id)
        if action.state_id is not None
        else None
    )
    assignee = (
        await _ensure_assignee_member(session, issues[0], action.assignee_id)
        if action.assignee_id is not None
        else None
    )
    add_labels = (
        await _ensure_labels(session, issues[0], list(action.add_label_ids))
        if action.add_label_ids
        else []
    )
    remove_labels = (
        await _ensure_labels(session, issues[0], list(action.remove_label_ids))
        if action.remove_label_ids
        else []
    )
    return _BulkContext(
        state=state,
        assignee=assignee,
        add_labels=add_labels,
        remove_labels=remove_labels,
        now=now,
    )


async def _apply_bulk_action_to_issue(
    session: AsyncSession,
    *,
    issue: Issue,
    actor_id: uuid.UUID,
    action: BulkAction,
    context: _BulkContext,
) -> None:
    """Apply the bulk action to one Issue (one Activity row per change).

    State changes go through the domain ``transition()`` (Issues already in
    the target State are skipped); archiving stamps ``archived_at``.
    """
    state, assignee, now = context.state, context.assignee, context.now
    if state is not None and issue.state_id != state.id:
        effect = transition(_to_rule(state), now)
        issue.state_id = state.id
        issue.completed_at = effect.completed_at
        issue.canceled_at = effect.canceled_at
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor_id,
                kind=ACTIVITY_ISSUE_STATE_CHANGED,
                field="state_id",
                from_value=issue.state.name,
                to_value=state.name,
            ),
        )
    if assignee is not None and issue.assignee_id != assignee.id:
        from_name = issue.assignee.display_name if issue.assignee else None
        issue.assignee_id = assignee.id
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="assignee_id",
                from_value=from_name,
                to_value=assignee.display_name,
            ),
        )
    if context.add_labels:
        current_ids = {label.id for label in issue.labels}
        for label in sorted(
            (item for item in context.add_labels if item.id not in current_ids),
            key=lambda item: item.name,
        ):
            issue.labels.append(label)
            record_activity(
                session,
                Activity(
                    issue_id=issue.id,
                    actor_id=actor_id,
                    kind=ACTIVITY_ISSUE_UPDATED,
                    field="label_id",
                    to_value=label.name,
                ),
            )
    if context.remove_labels:
        remove_ids = {label.id for label in context.remove_labels}
        removed = sorted(
            (label for label in issue.labels if label.id in remove_ids),
            key=lambda label: label.name,
        )
        issue.labels = [label for label in issue.labels if label.id not in remove_ids]
        for label in removed:
            record_activity(
                session,
                Activity(
                    issue_id=issue.id,
                    actor_id=actor_id,
                    kind=ACTIVITY_ISSUE_UPDATED,
                    field="label_id",
                    from_value=label.name,
                ),
            )
    if action.archive:
        issue.archived_at = now
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor_id,
                kind=ACTIVITY_ISSUE_UPDATED,
                field="archived_at",
                to_value=now.isoformat(),
            ),
        )


async def _ensure_state_in_team(
    session: AsyncSession, team: Team, state_id: uuid.UUID
) -> WorkflowState:
    """Load the target State; it must belong to the Team's Workflow."""
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
    return state
