"""Pure profile rules: theme validation, storage mapping, field normalisation."""

import pytest
from core.domain.errors import ValidationError
from core.domain.profile import (
    AVATAR_URL_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    MSG_INVALID_THEME,
    THEME_CHOICES,
    normalize_avatar_url,
    normalize_display_name,
    theme_from_storage,
    theme_to_storage,
    validate_theme,
)


def test_theme_choices_are_the_fixed_set() -> None:
    """The API exposes exactly system / light / dark."""
    assert THEME_CHOICES == ("system", "light", "dark")


def test_validate_theme_accepts_each_choice() -> None:
    """Every known preference round-trips unchanged."""
    for choice in THEME_CHOICES:
        assert validate_theme(choice) == choice


def test_validate_theme_none_resets_to_system() -> None:
    """An explicit null clears the preference back to system."""
    assert validate_theme(None) == "system"


def test_validate_theme_rejects_unknown_values() -> None:
    """Unknown preferences are a 400 ValidationError with the fixed message."""
    for value in ("blue", "Dark", "", "system "):
        with pytest.raises(ValidationError, match=MSG_INVALID_THEME):
            validate_theme(value)


def test_theme_storage_maps_system_to_null() -> None:
    """'system' is stored as NULL; the other preferences are stored as-is."""
    assert theme_to_storage("system") is None
    assert theme_to_storage("light") == "light"
    assert theme_to_storage("dark") == "dark"


def test_theme_from_storage_maps_null_to_system() -> None:
    """A NULL stored value means the user follows the system preference."""
    assert theme_from_storage(None) == "system"
    assert theme_from_storage("dark") == "dark"


def test_display_name_is_stripped() -> None:
    """Surrounding whitespace is not stored."""
    assert normalize_display_name("  Ada  ") == "Ada"


def test_display_name_blank_or_none_clears() -> None:
    """None and blank values clear the field to None."""
    assert normalize_display_name(None) is None
    assert normalize_display_name("") is None
    assert normalize_display_name("   ") is None


def test_display_name_over_the_limit_is_rejected() -> None:
    """Names longer than the limit are a 400 ValidationError."""
    with pytest.raises(ValidationError, match="display_name"):
        normalize_display_name("x" * (DISPLAY_NAME_MAX_LENGTH + 1))


def test_avatar_url_is_stripped() -> None:
    """Surrounding whitespace is not stored."""
    assert normalize_avatar_url("  https://example.com/a.png  ") == "https://example.com/a.png"


def test_avatar_url_blank_or_none_clears() -> None:
    """None and blank values clear the field to None."""
    assert normalize_avatar_url(None) is None
    assert normalize_avatar_url("  ") is None


def test_avatar_url_over_the_limit_is_rejected() -> None:
    """URLs longer than the limit are a 400 ValidationError."""
    with pytest.raises(ValidationError, match="avatar_url"):
        normalize_avatar_url("https://example.com/" + "x" * (AVATAR_URL_MAX_LENGTH + 1))
