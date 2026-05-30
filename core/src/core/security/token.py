from datetime import UTC, datetime, timedelta

import jwt

from core.settings import get_settings

settings = get_settings()


def create_access_token(data: dict, expires_delta: timedelta) -> str:
    """Create an access token with the given data and expires delta.

    Args:
        data: The data to encode.
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
