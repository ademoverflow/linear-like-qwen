"""JWT access tokens.

Claims: ``sub`` is the user id (UUID as string), ``email`` is informational. Tokens are not
revocable in v1 (see ADR 0002).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from core.settings import get_settings

settings = get_settings()


def create_access_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    """Create an access token with the given data and expires delta.

    Args:
        data: The claims to encode.
        expires_delta: The expiration time.

    Returns:
        The access token.

    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.core_jwt_secret_key,
        algorithm=settings.core_jwt_algorithm,
    )


def create_access_token_for_user(user_id: uuid.UUID, email: str) -> str:
    """Create the standard access token for a user, using the configured expiration."""
    return create_access_token(
        {"sub": str(user_id), "email": email},
        timedelta(minutes=settings.core_jwt_expiration_timedelta_minutes),
    )
