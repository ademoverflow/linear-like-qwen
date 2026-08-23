"""Actor loading: turn the authenticated User into the plain-data Actor."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Actor, Role
from core.models.membership import Membership
from core.models.user import User


async def load_actor(session: AsyncSession, user: User) -> Actor:
    """Build the ``Actor`` for ``user`` (id, admin flag, team roles)."""
    memberships = (
        await session.exec(select(Membership).where(Membership.user_id == user.id))
    ).all()
    return Actor(
        user_id=user.id,
        is_admin=user.is_admin,
        team_roles={m.team_id: Role(m.role) for m in memberships},
    )
