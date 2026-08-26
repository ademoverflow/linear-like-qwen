"""Team Membership use-cases (ticket 08, brief §5.2): add, role, remove, candidates."""

import uuid

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, Actor, Role, TeamResource, can
from core.domain.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from core.domain.memberships import MembershipRef, assert_not_last_owner
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.services.actors import load_actor

MSG_TEAM_NOT_FOUND = "Team not found"
MSG_TEAM_ARCHIVED = "Team is archived"
MSG_MEMBERS_OWNER_ONLY = "Only a Team owner or an Admin can manage members"
MSG_USER_NOT_FOUND = "User not found"
MSG_USER_DEACTIVATED = "The User is deactivated"
MSG_ALREADY_MEMBER = "The User is already a member of the Team"
MSG_ROLE_UNCHANGED = "The member already has that role"
MSG_LAST_OWNER = "A Team must keep at least one owner"


async def _visible_team(session: AsyncSession, *, actor: Actor, team_id: uuid.UUID) -> Team:
    """Load a Team the actor may manage (non-members/archived → 404, archived → 403)."""
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if team.archived_at is not None:
        raise ForbiddenError(MSG_TEAM_ARCHIVED)
    return team


async def _team_memberships(session: AsyncSession, team_id: uuid.UUID) -> list[Membership]:
    """Load all Memberships of a Team (in id order, the last-owner check input)."""
    return list((await session.exec(select(Membership).where(Membership.team_id == team_id))).all())


async def get_member_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Load a User by id (the routers build the member responses)."""
    user = (await session.exec(select(User).where(User.id == user_id))).one_or_none()
    if user is None:
        raise NotFoundError(MSG_USER_NOT_FOUND)
    return user


async def list_member_candidates(
    session: AsyncSession, *, user: User, team_id: uuid.UUID
) -> list[User]:
    """List the active Users who are not yet members of the Team (the add picker).

    ``GET /users`` is Admin-only, so this is the way a non-Admin owner sees
    the User base (ticket 08, recorded). Owner or Admin.

    Args:
        session: The database session.
        user: The authenticated acting user.
        team_id: The Team to pick candidates for.

    Returns:
        The candidate Users, by display name (falling back to email).

    Raises:
        NotFoundError: If the Team does not exist or is not visible to the
            actor (non-members get 404, not 403).
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.

    """
    actor = await load_actor(session, user)
    team = (await session.exec(select(Team).where(Team.id == team_id))).one_or_none()
    if team is None or not can(actor, Action.TEAM_VIEW, TeamResource(team.id)):
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    if not can(actor, Action.MEMBER_CANDIDATES, TeamResource(team.id)):
        raise ForbiddenError(MSG_MEMBERS_OWNER_ONLY)
    if team.archived_at is not None:
        raise ForbiddenError(MSG_TEAM_ARCHIVED)
    member_ids = [m.user_id for m in await _team_memberships(session, team.id)]
    statement = select(User).where(
        User.is_active.is_(True),  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
    )
    if member_ids:
        statement = statement.where(
            User.id.not_in(member_ids)  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
        )
    statement = statement.order_by(
        func.lower(func.coalesce(User.display_name, User.email)),  # type: ignore[union-attr]  # SQLModel field is a Column at runtime
    )
    return list((await session.exec(statement)).all())


async def add_team_member(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, user_id: uuid.UUID
) -> Membership:
    """Add an existing User to the Team as a ``member`` (brief §5.2).

    Owner or Admin. Existing Users only (the picker lists them); deactivated
    Users are rejected.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team to add the member to.
        user_id: The existing User to add.

    Returns:
        The created Membership.

    Raises:
        NotFoundError: If the Team or the User does not exist (or the Team
            is not visible to the actor).
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ValidationError: If the User is deactivated.
        ConflictError: If the User is already a member of the Team.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.MEMBER_ADD, TeamResource(team.id)):
            raise ForbiddenError(MSG_MEMBERS_OWNER_ONLY)
        target = (await session.exec(select(User).where(User.id == user_id))).one_or_none()
        if target is None:
            raise NotFoundError(MSG_USER_NOT_FOUND)
        if not target.is_active:
            raise ValidationError(MSG_USER_DEACTIVATED)
        existing = (
            await session.exec(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.team_id == team.id
                )
            )
        ).one_or_none()
        if existing is not None:
            raise ConflictError(MSG_ALREADY_MEMBER)
        membership = Membership(user_id=user_id, team_id=team.id, role=Role.MEMBER.value)
        session.add(membership)
        await session.flush()
        await session.refresh(membership)
        return membership


async def update_team_member_role(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, user_id: uuid.UUID, role: Role
) -> Membership:
    """Change a member's role (owner ↔ member).

    Owner or Admin. The Team must keep at least one owner: demoting the last
    owner is a 422 (brief §5.3's last-Admin rule, mirrored — including the
    owner demoting themselves).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team whose member is changed.
        user_id: The member to change.
        role: The new role.

    Returns:
        The updated Membership.

    Raises:
        NotFoundError: If the Team or the Membership does not exist.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        ValidationError: If the member already has that role.
        RuleViolationError: If the change would leave the Team without an
            owner.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.MEMBER_ROLE, TeamResource(team.id)):
            raise ForbiddenError(MSG_MEMBERS_OWNER_ONLY)
        membership = (
            await session.exec(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.team_id == team.id
                )
            )
        ).one_or_none()
        if membership is None:
            raise NotFoundError(MSG_USER_NOT_FOUND)
        if membership.role == role.value:
            raise ValidationError(MSG_ROLE_UNCHANGED)
        if role is Role.MEMBER:
            members = [
                MembershipRef(user_id=m.user_id, role=Role(m.role))
                for m in await _team_memberships(session, team.id)
            ]
            assert_not_last_owner(members, user_id)
        membership.role = role.value
        await session.flush()
        await session.refresh(membership)
        return membership


async def remove_team_member(
    session: AsyncSession, *, user: User, team_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Remove a member from the Team (204, ADR 0013).

    Owner or Admin. Removing the last owner is a 422 (brief §5.3 mirrored);
    an owner may remove themselves while another owner remains.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        team_id: The Team to remove the member from.
        user_id: The member to remove.

    Raises:
        NotFoundError: If the Team or the Membership does not exist.
        ForbiddenError: If the actor is not a Team owner (or Admin), or the
            Team is archived.
        RuleViolationError: If the change would leave the Team without an
            owner.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        team = await _visible_team(session, actor=actor, team_id=team_id)
        if not can(actor, Action.MEMBER_REMOVE, TeamResource(team.id)):
            raise ForbiddenError(MSG_MEMBERS_OWNER_ONLY)
        membership = (
            await session.exec(
                select(Membership).where(
                    Membership.user_id == user_id, Membership.team_id == team.id
                )
            )
        ).one_or_none()
        if membership is None:
            raise NotFoundError(MSG_USER_NOT_FOUND)
        if Role(membership.role) is Role.OWNER:
            members = [
                MembershipRef(user_id=m.user_id, role=Role(m.role))
                for m in await _team_memberships(session, team.id)
            ]
            assert_not_last_owner(members, user_id)
        await session.delete(membership)
        await session.flush()
