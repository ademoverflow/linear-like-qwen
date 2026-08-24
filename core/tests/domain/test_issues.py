"""Unit tests for the Issue input invariants (no database)."""

import pytest
from core.domain.errors import ValidationError
from core.domain.issues import (
    DESCRIPTION_MAX_LENGTH,
    PRIORITIES,
    validate_description,
    validate_estimate,
    validate_priority,
    validate_title,
)


def test_validate_title_trims_and_passes() -> None:
    """A normal title is trimmed and returned as-is."""
    assert validate_title("  Fix the login  ") == "Fix the login"


def test_validate_title_rejects_blank() -> None:
    """A blank or whitespace-only title is a 400."""
    with pytest.raises(ValidationError, match="1-255"):
        validate_title("   ")
    with pytest.raises(ValidationError, match="1-255"):
        validate_title("")


def test_validate_title_rejects_too_long() -> None:
    """A title over 255 chars is a 400."""
    with pytest.raises(ValidationError, match="1-255"):
        validate_title("x" * 256)
    assert len(validate_title("x" * 255)) == 255


def test_validate_description_allows_none_and_bounded_text() -> None:
    """None passes; text up to 50,000 chars passes."""
    assert validate_description(None) is None
    assert validate_description("a" * DESCRIPTION_MAX_LENGTH) == "a" * DESCRIPTION_MAX_LENGTH


def test_validate_description_rejects_too_long() -> None:
    """A description over 50,000 chars is a 400."""
    with pytest.raises(ValidationError, match="50,000"):
        validate_description("a" * (DESCRIPTION_MAX_LENGTH + 1))


@pytest.mark.parametrize("priority", PRIORITIES)
def test_validate_priority_accepts_known_values(priority: str) -> None:
    """Every documented priority value is accepted."""
    assert validate_priority(priority) == priority


def test_validate_priority_rejects_unknown() -> None:
    """An unknown priority is a 400."""
    with pytest.raises(ValidationError, match="Priority"):
        validate_priority("critical")


def test_validate_estimate_allows_none_and_range() -> None:
    """None passes; 0 and 21 pass."""
    assert validate_estimate(None) is None
    assert validate_estimate(0) == 0
    assert validate_estimate(21) == 21


def test_validate_estimate_rejects_out_of_range() -> None:
    """Estimates outside 0-21 are a 400."""
    with pytest.raises(ValidationError, match="Estimate"):
        validate_estimate(-1)
    with pytest.raises(ValidationError, match="Estimate"):
        validate_estimate(22)
