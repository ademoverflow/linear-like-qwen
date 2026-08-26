"""Profile rules (ticket 10): theme preference and profile field normalisation.

Pure module (ADR 0004): no I/O, unit-tested without a database.
"""

from core.domain.errors import ValidationError

#: The fixed set of theme preferences exposed by ``PATCH /auth/me``.
THEME_CHOICES: tuple[str, ...] = ("system", "light", "dark")

#: ``display_name`` length limit (matches the model field).
DISPLAY_NAME_MAX_LENGTH = 100

#: ``avatar_url`` length limit (matches the model field).
AVATAR_URL_MAX_LENGTH = 500

MSG_INVALID_THEME = "theme must be one of: system, light, dark"
MSG_DISPLAY_NAME_TOO_LONG = f"display_name must be at most {DISPLAY_NAME_MAX_LENGTH} characters"
MSG_AVATAR_URL_TOO_LONG = f"avatar_url must be at most {AVATAR_URL_MAX_LENGTH} characters"
MSG_UNKNOWN_PROFILE_FIELD = "Unknown profile field: {field}"


def validate_theme(value: str | None) -> str:
    """Validate a theme preference (``None`` resets to ``"system"``).

    Args:
        value: The preference from the request body.

    Returns:
        One of ``THEME_CHOICES``.

    Raises:
        ValidationError: If the value is not a known preference.

    """
    if value is None:
        return "system"
    if value not in THEME_CHOICES:
        raise ValidationError(MSG_INVALID_THEME)
    return value


def theme_to_storage(theme: str) -> str | None:
    """Map a preference to its stored form (``"system"`` is stored as NULL)."""
    return None if theme == "system" else theme


def theme_from_storage(stored: str | None) -> str:
    """Map the stored form back to a preference (NULL means ``"system"``)."""
    return "system" if stored is None else stored


def normalize_display_name(value: str | None) -> str | None:
    """Strip a display name; ``None`` or blank clears the field.

    Args:
        value: The value from the request body.

    Returns:
        The trimmed name, or ``None`` when cleared.

    Raises:
        ValidationError: If the trimmed name exceeds the length limit.

    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > DISPLAY_NAME_MAX_LENGTH:
        raise ValidationError(MSG_DISPLAY_NAME_TOO_LONG)
    return stripped


def normalize_avatar_url(value: str | None) -> str | None:
    """Strip an avatar URL; ``None`` or blank clears the field.

    Args:
        value: The value from the request body.

    Returns:
        The trimmed URL, or ``None`` when cleared.

    Raises:
        ValidationError: If the trimmed URL exceeds the length limit.

    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > AVATAR_URL_MAX_LENGTH:
        raise ValidationError(MSG_AVATAR_URL_TOO_LONG)
    return stripped
