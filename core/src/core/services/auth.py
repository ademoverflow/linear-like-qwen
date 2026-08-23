"""Auth use-cases: bootstrap/registration, login (rate-limited), session state."""

import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.errors import AuthenticationError, ForbiddenError, RateLimitError, ValidationError
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workspace import Workspace
from core.security.password import hash_password, verify_password
from core.security.token import create_access_token_for_user

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
MSG_INVITATIONS_NOT_ENABLED = "Registration is closed. Invitations are not available yet."
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
) -> User:
    """Create an account (bootstrap or invited; brief §5.1).

    While the user base is empty the first registrant becomes the workspace
    Admin. Afterwards registration is closed until Invitations exist
    (ticket 02); the ``token`` parameter is accepted for forward
    compatibility and is ignored for now.

    Args:
        session: The database session (the transaction is owned here).
        email: The account email.
        password: The plaintext password.
        token: Invitation token (used from ticket 02 on).

    Returns:
        The created user.

    Raises:
        ValidationError: If the user base is not empty (no open
            registration).

    """
    async with session.begin():
        user_count = (await session.exec(select(func.count()).select_from(User))).one()
        if user_count:
            message = MSG_REGISTRATION_CLOSED if token is None else MSG_INVITATIONS_NOT_ENABLED
            raise ValidationError(message)
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
        return user


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
