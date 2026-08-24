"""Tests for Label name/colour validation. No database required."""

import pytest
from core.domain.errors import ValidationError
from core.domain.labels import validate_label_color, validate_label_name


def test_validate_label_name_trims_and_passes() -> None:
    """A valid name is trimmed and returned."""
    assert validate_label_name("  bug  ") == "bug"
    assert validate_label_name("x" * 50) == "x" * 50


def test_validate_label_name_rejects_empty() -> None:
    """An empty (or whitespace-only) name is rejected."""
    for name in ("", "   "):
        with pytest.raises(ValidationError, match="1-50"):
            validate_label_name(name)


def test_validate_label_name_rejects_too_long() -> None:
    """Names longer than 50 characters are rejected."""
    with pytest.raises(ValidationError, match="1-50"):
        validate_label_name("x" * 51)


def test_validate_label_color_accepts_hex() -> None:
    """Both upper- and lower-case 6-digit hex values are accepted."""
    assert validate_label_color("#f2c94c") == "#f2c94c"
    assert validate_label_color("#ABCDEF") == "#ABCDEF"


@pytest.mark.parametrize(
    "color",
    ["f2c94c", "#f2c94", "#f2c94cc", "#gggggg", "#f2c94c ", "rgb(1,2,3)", ""],
)
def test_validate_label_color_rejects_bad_format(color: str) -> None:
    """Anything that is not #RRGGBB is rejected."""
    with pytest.raises(ValidationError, match="hex"):
        validate_label_color(color)
