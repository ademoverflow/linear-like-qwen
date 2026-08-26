"""Auth use-cases: bootstrap/registration, login (rate-limited), session state."""

import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.errors import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    RateLimitError,
    ValidationError,
)
from core.domain.invitations import invitation_state
from core.domain.profile import (
    MSG_UNKNOWN_PROFILE_FIELD,
    normalize_avatar_url,
    normalize_display_name,
    theme_to_storage,
    validate_theme,
)
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workspace import Workspace
from core.security.password import hash_password, verify_password
from core.security.token import create_access_token_for_user
from core.services.invitations import find_invitation_for_token, utcnow

# In-process login rate limit: 10 attempts / 15 min, per email and per client
# IP (ADR 0009). Not distributed: acceptable while v1 runs one core container.
LOGIN_RATE_LIMIT = 10
LOGIN_RATE_WINDOW = timedelta(minutes=15)


class SlidingWindowLimiter:
    """Count attempts per key over a sliding window (in-process, ADR 0009)."""

    def __init__(self, limit: int, window: timedelta) -> None:
        """Create a limiter with a per-key attempt budget.

        Args:
            limit: Maximum attempts per key within the window.
            window: The sliding window length.

        """
        self._limit = limit
        self._window_seconds = window.total_seconds()
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, key: str) -> None:
        """Record an attempt; raise when the window budget is exhausted.

        Args:
            key: The bucket key (e.g. ``email:foo@bar.baz`` or ``ip:1.2.3.4``).

        Raises:
            RateLimitError: When the key already made ``limit`` attempts in
                the window.

        """
        now = time.monotonic()
        with self._lock:
            bucket = self._timestamps[key]
            while bucket and now - bucket[0] > self._window_seconds:
                bucket.popleft()
            if len(bucket) >= self._limit:
                raise RateLimitError(MSG_RATE_LIMITED)
            bucket.append(now)

    def reset(self) -> None:
        """Clear all buckets (test hook)."""
        with self._lock:
            self._timestamps.clear()


MSG_REGISTRATION_CLOSED = "Registration is closed. A workspace admin must invite you first."
MSG_INVITATION_INVALID = "Invalid invitation token. Ask a workspace admin for a new one."
MSG_INVITATION_USED = "This invitation has already been used. Ask a workspace admin for a new one."
MSG_INVITATION_EXPIRED = "This invitation has expired. Ask a workspace admin for a new one."
MSG_INVITATION_EMAIL_MISMATCH = "This invitation was sent to a different email address."
MSG_EMAIL_TAKEN = "A user with this email already exists"
MSG_INVALID_CREDENTIALS = "Invalid email or password"
MSG_DEACTIVATED = "User account is deactivated"
MSG_RATE_LIMITED = "Too many login attempts. Please try again in a few minutes."

login_limiter = SlidingWindowLimiter(LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW)


def reset_login_rate_limiter() -> None:
    """Test hook: reset the login rate limiter between tests."""
    login_limiter.reset()


@dataclass(frozen=True)
class MembershipInfo:
    """A team membership as exposed by ``GET /auth/me``."""

    team_id: uuid.UUID
    team_key: str
    team_name: str
    role: str


async def register(
    session: AsyncSession, *, email: str, password: str, token: str | None = None
) -> tuple[User, str]:
    """Create an account: bootstrap while empty, otherwise via Invitation.

    While the user base is empty the first registrant becomes the workspace
    Admin. Afterwards registration requires a valid, unexpired, unused
    Invitation token (brief §5.1, ADR 0012); the registrant must use the
    invited email, and accepting the Invitation marks it used.

    Args:
        session: The database session (the transaction is owned here).
        email: The account email.
        password: The plaintext password.
        token: The raw Invitation token (required once bootstrap is closed).

    Returns:
        The created user and a fresh access token for their session.

    Raises:
        ValidationError: If registration is closed without a token, or the
            token is invalid, used, expired or for another email.
        ConflictError: If the invited email is already taken.

    """
    async with session.begin():
        user_count = (await session.exec(select(func.count()).select_from(User))).one()
        if user_count == 0:
            workspace = (await session.exec(select(Workspace).limit(1))).first()
            if workspace is None:
                session.add(Workspace())
            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_admin=True,
                display_name=email.split("@")[0],
            )
            session.add(user)
            await session.flush()
            return user, create_access_token_for_user(user.id, user.email)
        if token is None:
            raise ValidationError(MSG_REGISTRATION_CLOSED)
        invitation = await find_invitation_for_token(session, token)
        if invitation is None:
            raise ValidationError(MSG_INVITATION_INVALID)
        state = invitation_state(
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            now=utcnow(),
        )
        if state == "used":
            raise ValidationError(MSG_INVITATION_USED)
        if state == "expired":
            raise ValidationError(MSG_INVITATION_EXPIRED)
        normalized_email = email.strip().lower()
        if invitation.email != normalized_email:
            raise ValidationError(MSG_INVITATION_EMAIL_MISMATCH)
        existing = (await session.exec(select(User).where(User.email == normalized_email))).first()
        if existing is not None:
            raise ConflictError(MSG_EMAIL_TAKEN)
        user = User(
            email=normalized_email,
            hashed_password=hash_password(password),
            is_admin=False,
            display_name=normalized_email.split("@")[0],
        )
        session.add(user)
        invitation.accepted_at = utcnow()
        await session.flush()
        return user, create_access_token_for_user(user.id, user.email)


async def login(
    session: AsyncSession, *, email: str, password: str, client_ip: str
) -> tuple[User, str]:
    """Verify credentials and issue an access token (brief §5.1, ADR 0009).

    Args:
        session: The database session.
        email: The account email.
        password: The plaintext password.
        client_ip: The client's IP address (rate-limit bucket).

    Returns:
        The user and a fresh access token.

    Raises:
        RateLimitError: When the per-email or per-IP budget is exhausted.
        AuthenticationError: When the credentials are invalid.
        ForbiddenError: When the account is deactivated.

    """
    login_limiter.consume(f"email:{email.lower()}")
    login_limiter.consume(f"ip:{client_ip}")
    user = (await session.exec(select(User).where(User.email == email))).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError(MSG_INVALID_CREDENTIALS)
    if not user.is_active:
        raise ForbiddenError(MSG_DEACTIVATED)
    token = create_access_token_for_user(user.id, user.email)
    return user, token


async def get_me(session: AsyncSession, user: User) -> list[MembershipInfo]:
    """Return the user's team memberships (for ``GET /auth/me``).

    Args:
        session: The database session.
        user: The authenticated user.

    Returns:
        One ``MembershipInfo`` per Team the user belongs to.

    """
    memberships = (
        await session.exec(select(Membership).where(Membership.user_id == user.id))
    ).all()
    if not memberships:
        return []
    team_ids = [m.team_id for m in memberships]
    teams = (
        await session.exec(select(Team).where(Team.id.in_(team_ids)))  # type: ignore[attr-defined]
    ).all()
    teams_by_id = {team.id: team for team in teams}
    return [
        MembershipInfo(
            team_id=m.team_id,
            team_key=teams_by_id[m.team_id].key,
            team_name=teams_by_id[m.team_id].name,
            role=m.role,
        )
        for m in memberships
    ]


async def registration_status(session: AsyncSession) -> bool:
    """Whether bootstrap registration is open (user base still empty)."""
    user_count = (await session.exec(select(func.count()).select_from(User))).one()
    return user_count == 0


PROFILE_FIELDS = {"display_name", "avatar_url", "theme"}


async def update_me(session: AsyncSession, *, user: User, changes: dict[str, Any]) -> User:
    """Update the authenticated user's own profile (brief §9, ticket 10).

    Only ``display_name``, ``avatar_url`` and ``theme`` are accepted (``None``
    clears a nullable field). The theme is validated against the fixed set;
    ``"system"`` is stored as NULL. No Activity rows: a profile change is not
    an Issue Activity (``issue_id`` is NOT NULL). No authorization action:
    the endpoint is gated by the auth dependency and only ever updates the
    caller.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user (detached; re-loaded here).
        changes: Field name to new value, only for the fields the client
            sent (``None`` clears).

    Returns:
        The updated user (managed in the session, attributes refreshed).

    Raises:
        ValidationError: If a field is unknown or a value is invalid.

    """
    async with session.begin():
        target = (await session.exec(select(User).where(User.id == user.id))).one()
        for name, value in changes.items():
            if name == "display_name":
                target.display_name = normalize_display_name(value)
            elif name == "avatar_url":
                target.avatar_url = normalize_avatar_url(value)
            elif name == "theme":
                target.theme = theme_to_storage(validate_theme(value))
            else:
                raise ValidationError(MSG_UNKNOWN_PROFILE_FIELD.format(field=name))
        await session.flush()
        await session.refresh(target)
        return target
