"""Invitation use-cases (ADR 0012): invite by email, list, token lookup.

The raw token is returned once at creation (the Admin shares it with the
invitee); only its SHA-256 hex digest is stored.
"""

from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.authz import Action, can
from core.domain.errors import ForbiddenError
from core.domain.invitations import generate_token, hash_token
from core.models.invitation import Invitation
from core.models.user import User
from core.services.actors import load_actor

# Invitations are usable for 7 days after being created (ADR 0012).
INVITATION_TTL = timedelta(days=7)

MSG_ADMIN_ONLY = "Only workspace admins can manage Invitations"


def utcnow() -> datetime:
    """Get the current instant in UTC (timezone-aware)."""
    return datetime.now(UTC)


async def invite_user(session: AsyncSession, *, user: User, email: str) -> tuple[Invitation, str]:
    """Create an Invitation for ``email``, or replace the active one (ADR 0012).

    Re-inviting the same email replaces the token, so the old one stops
    working; the new expiry is ``now + 7 days``.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        email: The invitee's email.

    Returns:
        The Invitation and the plain token (shown to the Admin once).

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.

    """
    normalized_email = email.strip().lower()
    async with session.begin():
        actor = await load_actor(session, user)
        if not can(actor, Action.INVITATION_CREATE, None):
            raise ForbiddenError(MSG_ADMIN_ONLY)
        existing = (
            await session.exec(
                select(Invitation).where(
                    Invitation.email == normalized_email,
                    Invitation.accepted_at.is_(None),  # type: ignore[union-attr]  # SQLModel field is a Column at runtime
                )
            )
        ).first()
        plain_token = generate_token()
        expires_at = utcnow() + INVITATION_TTL
        if existing is not None:
            existing.token = hash_token(plain_token)
            existing.invited_by = actor.user_id
            existing.expires_at = expires_at
            invitation = existing
        else:
            invitation = Invitation(
                email=normalized_email,
                token=hash_token(plain_token),
                invited_by=actor.user_id,
                expires_at=expires_at,
            )
            session.add(invitation)
        await session.flush()
        return invitation, plain_token


async def list_invitations(session: AsyncSession, *, user: User) -> list[Invitation]:
    """List all Invitations, newest first (Admin screen).

    Args:
        session: The database session.
        user: The authenticated acting user.

    Returns:
        Every Invitation (pending, expired and accepted).

    Raises:
        ForbiddenError: If the actor is not a workspace Admin.

    """
    actor = await load_actor(session, user)
    if not can(actor, Action.INVITATION_LIST, None):
        raise ForbiddenError(MSG_ADMIN_ONLY)
    statement = select(Invitation).order_by(Invitation.created_at.desc())  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
    return list((await session.exec(statement)).all())


async def find_invitation_for_token(session: AsyncSession, token: str) -> Invitation | None:
    """Look up the Invitation for a raw token (compared as its hash).

    The row is locked (``SELECT ... FOR UPDATE``) so two concurrent
    registers with the same token cannot both see it as unused.
    """
    return (
        await session.exec(
            select(Invitation).where(Invitation.token == hash_token(token)).with_for_update()
        )
    ).first()
