"""Workflow State use-cases (ticket 08, brief §4.3): add, edit, reorder, delete-with-migrate.

Every State edit is version-guarded (ADR 0008): the caller echoes the
last-seen ``version`` of each State they change and a stale version is a
409. The service bumps ``version`` on every State-row change (no DB
trigger). All mutations are owner-gated (Admins pass) and refuse archived
Teams.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Actor, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.workflow import (
    Category,
    WorkflowStateRule,
    assert_migration_target_same_category,
    transition,
    validate_category,
    validate_category_change,
    validate_state_color,
    validate_state_deletion,
    validate_state_name,
)
from core.models.activity import Activity
from core.models.issue import Issue
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.services.activity import record_activity
from core.services.actors import load_actor

MSG_TEAM_NOT_FOUND = "Team not found"
MSG_TEAM_ARCHIVED = "Team is archived"
MSG_STATES_OWNER_ONLY = "Only a Team owner or an Admin can edit the Workflow"
MSG_STATE_NOT_FOUND = "State not found"
MSG_STATE_STALE = "The State was changed by someone else. Reload and try again."
MSG_STATE_NAME_EXISTS = "A State with this name already exists"
MSG_STATE_UPDATE_EMPTY = "Provide a name, a colour and/or a category to update"
MSG_REORDER_UNCHANGED = "The State order is already up to date"
MSG_REORDER_INCOMPLETE = "The reorder must list every State of the Workflow exactly once"
MSG_MIGRATION_REQUIRED = "The State still has Issues; choose a State to migrate them to"
MSG_MIGRATION_NOT_NEEDED = "The State has no Issues; no migration target needed"
MSG_TARGET_NOT_IN_TEAM = "The migration target must be a State of the same Team"
MSG_MIGRATE_TO_SELF = "The migration target must be a different State"
ACTIVITY_ISSUE_STATE_CHANGED = "issue.state_changed"


@dataclass(frozen=True)
class StateRef:
    """A State id with the version the caller last saw (ADR 0008)."""

    id: uuid.UUID
    version: int


async def _writable_team(session: AsyncSession, *, actor: Actor, team_id: uuid.UUID) -> Team:
    """Load a Team for a State edit (non-member → 404, archived → 403)."""
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if team.archived_at is not None:
        raise ForbiddenError(MSG_TEAM_ARCHIVED)
    return team


async def _locked_workflow(session: AsyncSession, team: Team) -> Workflow:
    """Lock the Team's Workflow row (serialises concurrent State edits)."""
    return (
        await session.exec(select(Workflow).where(Workflow.team_id == team.id).with_for_update())
    ).one()


async def _workflow_states(session: AsyncSession, workflow: Workflow) -> list[WorkflowState]:
    """Load a Workflow's States in position order."""
    return list(
        await session.exec(
            select(WorkflowState)
            .where(WorkflowState.workflow_id == workflow.id)
            .order_by(WorkflowState.position)  # type: ignore[attr-defined,arg-type]  # SQLModel field is a Column at runtime
        )
    )


async def _state_in_workflow(
    session: AsyncSession, *, state_id: uuid.UUID, workflow: Workflow
) -> WorkflowState:
    state = (
        await session.exec(
            select(WorkflowState).where(
                WorkflowState.id == state_id, WorkflowState.workflow_id == workflow.id
            )
        )
    ).one_or_none()
    if state is None:
        raise NotFoundError(MSG_STATE_NOT_FOUND)
    return state


async def _bump_version(session: AsyncSession, state: WorkflowState) -> None:
    """Bump a State's version and refresh it (no DB trigger; ADR 0008)."""
    state.version = state.version + 1
    await session.flush()
    await session.refresh(state, ["version", "created_at", "updated_at"])


async def create_team_state(  # noqa: PLR0913  # house service shape: session, actor, payload fields
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    name: str,
    category: str,
    color: str,
) -> WorkflowState:
    """Add a Workflow State at the end of the Team's Workflow (brief §4.3).

    Appends at ``position = max + 1``; no version echo (it changes no
    existing State — ADR 0008), the Workflow row is locked so concurrent
    appends serialise on position allocation.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        team_id: The Team whose Workflow grows.
        name: The State name (1-50 chars, trimmed, unique per Workflow).
        category: One of the five categories.
        color: The State colour (``#RRGGBB``).

    Returns:
        The created State (``version`` 1).

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ValidationError: If the name or colour is invalid.
        ConflictError: If the name is already taken in the Workflow.

    """
    clean_name = validate_state_name(name)
    clean_category = validate_category(category)
    validate_state_color(color)
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _writable_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.STATE_CREATE, TeamResource(team.id)):
            raise ForbiddenError(MSG_STATES_OWNER_ONLY)
        workflow = await _locked_workflow(session, team)
        states = await _workflow_states(session, workflow)
        if any(s.name == clean_name for s in states):
            raise ConflictError(MSG_STATE_NAME_EXISTS)
        next_position = max((s.position for s in states), default=-1) + 1
        state = WorkflowState(
            workflow_id=workflow.id,
            name=clean_name,
            category=clean_category,
            color=color,
            position=next_position,
        )
        session.add(state)
        await session.flush()
        await session.refresh(state)
        return state


async def update_team_state(  # noqa: PLR0913  # house service shape: session, actor, payload fields
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    state_id: uuid.UUID,
    version: int,
    name: str | None,
    color: str | None,
    category: str | None,
) -> WorkflowState:
    """Rename / recolor / re-categorise a Workflow State (brief §4.3).

    The caller must echo the last-seen ``version``; a stale version is a
    409 (ADR 0008). A category change enforces the category minimum (422).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        team_id: The Team whose State is edited.
        state_id: The State to edit.
        version: The ``version`` the client last saw.
        name: The new name, if sent.
        color: The new colour, if sent.
        category: The new category, if sent.

    Returns:
        The updated State (with the bumped ``version``).

    Raises:
        NotFoundError: If the Team or the State does not exist.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ConflictError: If ``version`` is stale.
        ValidationError: If an input is invalid or nothing was sent.
        ConflictError: If the new name collides with another State.
        RuleViolationError: If the category change would empty a required
            category.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _writable_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.STATE_EDIT, TeamResource(team.id)):
            raise ForbiddenError(MSG_STATES_OWNER_ONLY)
        workflow = await _locked_workflow(session, team)
        state = await _state_in_workflow(session, state_id=state_id, workflow=workflow)
        if state.version != version:
            raise ConflictError(MSG_STATE_STALE)

        changed = False
        if name is not None:
            clean_name = validate_state_name(name)
            if clean_name != state.name:
                if any(
                    s.name == clean_name and s.id != state.id
                    for s in await _workflow_states(session, workflow)
                ):
                    raise ConflictError(MSG_STATE_NAME_EXISTS)
                state.name = clean_name
                changed = True
        if color is not None:
            clean_color = validate_state_color(color)
            if clean_color != state.color:
                state.color = clean_color
                changed = True
        if category is not None:
            clean_category = validate_category(category)
            if clean_category != state.category:
                states = [_to_rule(s) for s in await _workflow_states(session, workflow)]
                validate_category_change(states, _to_rule(state), clean_category)
                state.category = clean_category
                changed = True
        if not changed:
            raise ValidationError(MSG_STATE_UPDATE_EMPTY)
        await _bump_version(session, state)
        return state


async def reorder_team_states(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, states: list[StateRef]
) -> list[WorkflowState]:
    """Reorder the Team's Workflow States by drag (brief §4.3, ADR 0008).

    The body carries the **full** ordered list; every entry echoes the
    last-seen ``version`` of its State (any stale → 409). Positions are
    rewritten offset-then-settle so the unique ``(workflow_id, position)``
    index never sees a duplicate.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        team_id: The Team whose Workflow is reordered.
        states: The full desired order (id + last-seen version).

    Returns:
        The Workflow States in the new order.

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ValidationError: If the list is not exactly the Workflow's States.
        ConflictError: If any echoed ``version`` is stale.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _writable_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.STATE_EDIT, TeamResource(team.id)):
            raise ForbiddenError(MSG_STATES_OWNER_ONLY)
        workflow = await _locked_workflow(session, team)
        current = await _workflow_states(session, workflow)
        by_id = {s.id: s for s in current}

        seen: set[uuid.UUID] = set()
        for ref in states:
            if ref.id in seen:
                raise ValidationError(MSG_REORDER_INCOMPLETE)
            seen.add(ref.id)
            if ref.id not in by_id:
                raise ValidationError(MSG_REORDER_INCOMPLETE)
        if len(states) != len(current):
            raise ValidationError(MSG_REORDER_INCOMPLETE)
        for ref in states:
            if by_id[ref.id].version != ref.version:
                raise ConflictError(MSG_STATE_STALE)

        new_positions = {ref.id: index for index, ref in enumerate(states)}
        changed = [s for s in current if new_positions[s.id] != s.position]
        if not changed:
            raise ValidationError(MSG_REORDER_UNCHANGED)

        count = len(current)
        # Offset-then-settle with a flush in between: SQLAlchemy batches
        # attribute changes into final values per row, so without the
        # intermediate flush the settle could land on a position another
        # row still holds (unique (workflow_id, position) violation).
        for state in current:
            state.position = state.position + count
        await session.flush()
        for ref in states:
            by_id[ref.id].position = new_positions[ref.id]
        for state in changed:
            state.version = state.version + 1
        await session.flush()
        for state in current:
            await session.refresh(state, ["position", "version", "created_at", "updated_at"])
        return [by_id[ref.id] for ref in states]


async def delete_team_state(  # noqa: PLR0913  # house service shape: session, actor, payload fields
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    state_id: uuid.UUID,
    version: int,
    migrate_to_state_id: uuid.UUID | None,
) -> None:
    """Delete a Workflow State, migrating its Issues (brief §4.3).

    A State that still has Issues (archived or not — the ``state_id`` FK is
    not cascading) only deletes with a ``migrate_to_state_id`` of the same
    category, in one transaction. Every moved non-archived Issue goes
    through the domain ``transition()`` and emits one ``issue.state_changed``
    Activity; **archived** Issues move to the same target as well but emit no
    Activity and keep their bookkeeping timestamps (ticket 08, recorded).
    Deleting a State that would empty a
    required category is a 422.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (Team owner or Admin).
        team_id: The Team whose State is deleted.
        state_id: The State to delete.
        version: The ``version`` the client last saw.
        migrate_to_state_id: The same-category target for the State's
            Issues (required while any Issue, archived or not, remains).

    Raises:
        NotFoundError: If the Team or the State does not exist.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ConflictError: If ``version`` is stale.
        ValidationError: If the migration target is missing or not needed,
            or invalid.
        RuleViolationError: If the category minimum would be broken.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _writable_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.STATE_DELETE, TeamResource(team.id)):
            raise ForbiddenError(MSG_STATES_OWNER_ONLY)
        workflow = await _locked_workflow(session, team)
        state = await _state_in_workflow(session, state_id=state_id, workflow=workflow)
        if state.version != version:
            raise ConflictError(MSG_STATE_STALE)

        issues_in_state = list(
            await session.exec(
                select(Issue).where(Issue.state_id == state.id).order_by(Issue.number)  # type: ignore[attr-defined,arg-type]  # SQLModel field is a Column at runtime
            )
        )

        target: WorkflowState | None = None
        if issues_in_state:
            if migrate_to_state_id is None:
                raise ValidationError(MSG_MIGRATION_REQUIRED)
            target = (
                await session.exec(
                    select(WorkflowState).where(
                        WorkflowState.id == migrate_to_state_id,
                        WorkflowState.workflow_id == workflow.id,
                    )
                )
            ).one_or_none()
            if target is None:
                raise ValidationError(MSG_TARGET_NOT_IN_TEAM)
            if target.id == state.id:
                raise ValidationError(MSG_MIGRATE_TO_SELF)
            assert_migration_target_same_category(_to_rule(state), _to_rule(target))
        elif migrate_to_state_id is not None:
            raise ValidationError(MSG_MIGRATION_NOT_NEEDED)

        rules = [_to_rule(s) for s in await _workflow_states(session, workflow)]
        validate_state_deletion(rules, _to_rule(state))

        if target is not None:
            effect = transition(_to_rule(target), datetime.now(UTC))
            for issue in issues_in_state:
                issue.state_id = target.id
                if issue.archived_at is None:
                    # Bookkeeping and Activity are for active Issues only;
                    # archived Issues keep their timestamps (ticket 08).
                    issue.completed_at = effect.completed_at
                    issue.canceled_at = effect.canceled_at
                    record_activity(
                        session,
                        Activity(
                            issue_id=issue.id,
                            actor_id=actor.user_id,
                            kind=ACTIVITY_ISSUE_STATE_CHANGED,
                            field="state_id",
                            from_value=state.name,
                            to_value=target.name,
                        ),
                    )
        await session.delete(state)
        await session.flush()


def _to_rule(state: WorkflowState) -> WorkflowStateRule:
    """Map an ORM WorkflowState to the plain domain record."""
    return WorkflowStateRule(
        name=state.name,
        category=cast("Category", state.category),
        color=state.color,
        position=state.position,
    )
