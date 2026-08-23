"""User management use-cases (brief §5.3).

List, deactivate/reactivate, promote/demote with the last-active-Admin
protection.
"""

import uuid

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, can
from core.domain.errors import ForbiddenError, NotFoundError
from core.domain.users import assert_last_admin_rule
from core.models.user import User
from core.services.actors import load_actor

MSG_ADMIN_ONLY = "Only workspace admins can manage Users"
MSG_USER_NOT_FOUND = "User not found"


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Load a User by id or raise ``NotFoundError`` (404)."""
    user = (await session.exec(select(User).where(User.id == user_id))).first()
    if user is None:
        raise NotFoundError(MSG_USER_NOT_FOUND)
    return user


async def _other_active_admin_count(session: AsyncSession, exclude_id: uuid.UUID) -> int:
    """Active Admins besides the excluded User."""
    return (
        await session.exec(
            select(func.count())
            .select_from(User)
            .where(
                User.is_admin.is_(True),  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
                User.is_active.is_(True),  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
                User.id != exclude_id,
            )
        )
    ).one()


async def list_users(session: AsyncSession, *, user: User) -> list[User]:
    """List every User (active and deactivated), oldest first (brief §5.3).

    Args:
        session: The database session.
        user: The authenticated acting user.

    Returns:
        All Users in the Workspace.

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.

    """
    actor = await load_actor(session, user)
    if not can(actor, Action.USER_LIST, None):
        raise ForbiddenError(MSG_ADMIN_ONLY)
    statement = select(User).order_by(User.created_at)  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
    return list((await session.exec(statement)).all())


async def set_user_active(
    session: AsyncSession, *, user: User, target_id: uuid.UUID, active: bool
) -> User:
    """Deactivate (``active=False``) or reactivate (``active=True``) a User.

    Deactivating the last active Admin is rejected with 422 (brief §5.3).
    Deactivated Users keep their Comments and Activity (history stays intact).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        target_id: The User to change.
        active: The new ``is_active`` value.

    Returns:
        The updated User.

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.
        NotFoundError: If no User has the id.
        RuleViolationError: If the change would leave no active Admin.

    """
    action = Action.USER_REACTIVATE if active else Action.USER_DEACTIVATE
    async with session.begin():
        actor = await load_actor(session, user)
        if not can(actor, action, None):
            raise ForbiddenError(MSG_ADMIN_ONLY)
        target = await _get_user(session, target_id)
        if not active:
            assert_last_admin_rule(
                target_is_admin=target.is_admin,
                target_is_active=target.is_active,
                other_active_admins=await _other_active_admin_count(session, target.id),
            )
        target.is_active = active
        await session.flush()
        return target


async def set_user_admin(
    session: AsyncSession, *, user: User, target_id: uuid.UUID, is_admin: bool
) -> User:
    """Promote (``is_admin=True``) or demote (``is_admin=False``) a User.

    Demoting the last active Admin is rejected with 422 (brief §5.3).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        target_id: The User to change.
        is_admin: The new ``is_admin`` value.

    Returns:
        The updated User.

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.
        NotFoundError: If no User has the id.
        RuleViolationError: If the change would leave no active Admin.

    """
    action = Action.USER_PROMOTE if is_admin else Action.USER_DEMOTE
    async with session.begin():
        actor = await load_actor(session, user)
        if not can(actor, action, None):
            raise ForbiddenError(MSG_ADMIN_ONLY)
        target = await _get_user(session, target_id)
        if not is_admin:
            assert_last_admin_rule(
                target_is_admin=target.is_admin,
                target_is_active=target.is_active,
                other_active_admins=await _other_active_admin_count(session, target.id),
            )
        target.is_admin = is_admin
        await session.flush()
        return target
