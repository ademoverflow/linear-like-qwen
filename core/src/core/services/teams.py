"""Team use-cases (brief §6): creation with Workflow seeding, listing."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Actor, Role, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.identifiers import is_valid_team_key
from core.domain.workflow import DEFAULT_WORKFLOW_STATES
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.services.actors import load_actor

MSG_ADMIN_ONLY = "Only workspace admins can create Teams"
MSG_TEAM_NOT_FOUND = "Team not found"
MSG_TEAM_ARCHIVED = "Team is archived"
MSG_TEAM_NOT_ARCHIVED = "Team is not archived"
MSG_NAME_INVALID = "Team name must be 1-100 characters"
MSG_KEY_INVALID = "Team key must be 2-5 uppercase letters (A-Z)"
MSG_KEY_EXISTS = "A Team with this key already exists"
MSG_TEAM_UPDATE_EMPTY = "Provide a name and/or a description to update"
MSG_TEAM_UPDATE_FORBIDDEN = "Only a Team owner or an Admin can edit the Team"
MSG_ARCHIVE_FORBIDDEN = "Only an Admin can archive a Team"
MSG_RESTORE_FORBIDDEN = "Only an Admin can restore a Team"
TEAM_NAME_MAX_LENGTH = 100
TEAM_DESCRIPTION_MAX_LENGTH = 5000


async def create_team(
    session: AsyncSession, *, user: User, name: str, key: str, description: str | None
) -> Team:
    """Create a Team with its default Workflow and the owner Membership.

    The creating Admin becomes ``owner``; the six default Workflow States are
    seeded in the same transaction (brief §4.1, ADR 0005).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        name: Team name (1-100 chars, trimmed).
        key: Team key (2-5 uppercase letters, unique, immutable).
        description: Optional description.

    Returns:
        The created Team.

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.
        ValidationError: If the name or key is invalid.
        ConflictError: If the key is already taken.

    """
    name = name.strip()
    if not name or len(name) > TEAM_NAME_MAX_LENGTH:
        raise ValidationError(MSG_NAME_INVALID)
    if not is_valid_team_key(key):
        raise ValidationError(MSG_KEY_INVALID)
    clean_description = description.strip() if description and description.strip() else None

    async with session.begin():
        actor = await load_actor(session, user)
        if not can(actor, Action.TEAM_CREATE, None):
            raise ForbiddenError(MSG_ADMIN_ONLY)
        existing = (await session.exec(select(Team).where(Team.key == key))).first()
        if existing is not None:
            raise ConflictError(MSG_KEY_EXISTS)
        team = Team(name=name, key=key, description=clean_description)
        session.add(team)
        await session.flush()

        workflow = Workflow(team_id=team.id)
        session.add(workflow)
        await session.flush()
        for state_rule in DEFAULT_WORKFLOW_STATES:
            session.add(
                WorkflowState(
                    workflow_id=workflow.id,
                    name=state_rule.name,
                    category=state_rule.category,
                    color=state_rule.color,
                    position=state_rule.position,
                )
            )
        session.add(Membership(user_id=actor.user_id, team_id=team.id, role=Role.OWNER.value))
        await session.flush()
        return team


async def get_team(session: AsyncSession, *, user: User, team_id: uuid.UUID) -> Team:
    """Fetch a Team's detail (ticket 08; Settings page).

    Archived Teams stay visible to Admins (who see them in the list and can
    restore them); for everyone else an archived Team is a 404, like an
    unknown one.

    Args:
        session: The database session.
        user: The authenticated acting user.
        team_id: The Team to fetch.

    Returns:
        The Team.

    Raises:
        NotFoundError: If the Team does not exist, is not visible to the
            actor, or is archived (for non-Admins).

    """
    actor = await load_actor(session, user)
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if team.archived_at is not None and not actor.is_admin:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    return team


TEAM_UPDATE_FIELDS: tuple[str, ...] = ("name", "description")


async def update_team(
    session: AsyncSession,
    *,
    user: User,
    team_id: uuid.UUID,
    changes: dict[str, Any],
) -> Team:
    """Edit a Team's name and/or description (brief §5.2).

    The key is immutable and has no API field. Owner or Admin. Only the
    fields the client sent are in ``changes`` (the router filters via
    ``model_fields_set``); an explicit ``description = None`` clears it,
    and ``name`` may not be cleared.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team to edit.
        changes: Field name to new value for the fields the client sent.

    Returns:
        The updated Team.

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor (non-members get 404, not 403).
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ValidationError: If the name is invalid or nothing was sent.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
        if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
            raise NotFoundError(MSG_TEAM_NOT_FOUND)
        if not can(actor, Action.TEAM_UPDATE, TeamResource(team.id)):
            raise ForbiddenError(MSG_TEAM_UPDATE_FORBIDDEN)
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        if not changes:
            raise ValidationError(MSG_TEAM_UPDATE_EMPTY)
        if "name" in changes:
            clean_name = (changes["name"] or "").strip()
            if not clean_name or len(clean_name) > TEAM_NAME_MAX_LENGTH:
                raise ValidationError(MSG_NAME_INVALID)
            team.name = clean_name
        if "description" in changes:
            raw_description = changes["description"]
            team.description = (
                raw_description.strip() if raw_description and raw_description.strip() else None
            )
        await session.flush()
        await session.refresh(team)
        return team


async def archive_team(session: AsyncSession, *, user: User, team_id: uuid.UUID) -> Team:
    """Archive a Team (soft hide, brief §6): sets ``archived_at``.

    Admin only; reversible via ``restore_team``. The Team and its Issues
    keep their data; the Team is hidden everywhere for non-Admins.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team to archive.

    Returns:
        The updated Team.

    Raises:
        NotFoundError: If the Team does not exist, is not visible to the
            actor, or is already archived.
        ForbiddenError: If the actor is not a workspace Admin.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
        if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
            raise NotFoundError(MSG_TEAM_NOT_FOUND)
        if not can(actor, Action.TEAM_ARCHIVE, TeamResource(team.id)):
            raise ForbiddenError(MSG_ARCHIVE_FORBIDDEN)
        if team.archived_at is not None:
            raise NotFoundError(MSG_TEAM_NOT_FOUND)
        team.archived_at = datetime.now(UTC)
        await session.flush()
        await session.refresh(team)
        return team


async def restore_team(session: AsyncSession, *, user: User, team_id: uuid.UUID) -> Team:
    """Restore an archived Team (brief §6): clears ``archived_at``.

    Admin only (the one who may archive may restore).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team to restore.

    Returns:
        The updated Team.

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor.
        ForbiddenError: If the actor is not a workspace Admin.
        ValidationError: If the Team is not archived.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
        if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
            raise NotFoundError(MSG_TEAM_NOT_FOUND)
        if not can(actor, Action.TEAM_RESTORE, TeamResource(team.id)):
            raise ForbiddenError(MSG_RESTORE_FORBIDDEN)
        if team.archived_at is None:
            raise ValidationError(MSG_TEAM_NOT_ARCHIVED)
        team.archived_at = None
        await session.flush()
        await session.refresh(team)
        return team


async def list_teams(session: AsyncSession, *, user: User) -> list[Team]:
    """List the Teams visible to the actor, ordered by name.

    Members see only their own Teams; Admins see all Teams, archived ones
    included (the sidebar badges them so Restore stays reachable — ticket
    08, recorded deviation from "hidden everywhere" for the Admin view).

    Args:
        session: The database session.
        user: The authenticated acting user.

    Returns:
        The visible Teams, ordered by name.

    """
    actor = await load_actor(session, user)
    statement = select(Team).order_by(Team.name)
    if not actor.is_admin:
        statement = statement.where(Team.archived_at.is_(None))  # type: ignore[union-attr]
        team_ids = list(actor.team_roles)
        if not team_ids:
            return []
        statement = statement.where(Team.id.in_(team_ids))  # type: ignore[attr-defined]
    return list((await session.exec(statement)).all())


async def _visible_team(session: AsyncSession, *, actor: Actor, team_id: uuid.UUID) -> Team:
    """Load a Team the actor may read (non-members and archived → 404)."""
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if team.archived_at is not None:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    return team


async def list_team_states(
    session: AsyncSession, *, user: User, team_id: uuid.UUID
) -> list[WorkflowState]:
    """List a Team's Workflow States in position order (board columns; ADR 0011).

    Args:
        session: The database session.
        user: The authenticated acting user (Team member or Admin).
        team_id: The Team to list States for.

    Returns:
        The Team's Workflow States ordered by position.

    Raises:
        NotFoundError: If the Team does not exist, is not visible to the
            actor (non-members get 404, not 403), or is archived.

    """
    actor = await load_actor(session, user)
    team = await _visible_team(session, actor=actor, team_id=team_id)
    workflow = (await session.exec(select(Workflow).where(Workflow.team_id == team.id))).one()
    return list(
        await session.exec(
            select(WorkflowState)
            .where(WorkflowState.workflow_id == workflow.id)
            .order_by(WorkflowState.position)  # type: ignore[attr-defined,arg-type]  # SQLModel field is a Column at runtime
        )
    )


async def list_team_members(
    session: AsyncSession, *, user: User, team_id: uuid.UUID
) -> list[tuple[User, Role]]:
    """List a Team's members with their roles (ticket 03 assignee picker).

    Args:
        session: The database session.
        user: The authenticated acting user (Team member or Admin).
        team_id: The Team to list members for.

    Returns:
        The Team's members (User with their Membership role), sorted by
        display name.

    Raises:
        NotFoundError: If the Team does not exist, is not visible to the
            actor (non-members get 404, not 403), or is archived.

    """
    actor = await load_actor(session, user)
    team = await _visible_team(session, actor=actor, team_id=team_id)
    memberships = list(
        (await session.exec(select(Membership).where(Membership.team_id == team.id))).all()
    )
    if not memberships:
        return []
    member_ids = [membership.user_id for membership in memberships]
    users = (
        await session.exec(select(User).where(User.id.in_(member_ids)))  # type: ignore[attr-defined]
    ).all()
    user_by_id = {user.id: user for user in users}
    ordered = sorted(memberships, key=lambda m: user_by_id[m.user_id].display_name or "")
    return [(user_by_id[m.user_id], Role(m.role)) for m in ordered]
