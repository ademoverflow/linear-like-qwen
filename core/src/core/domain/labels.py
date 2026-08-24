"""Label input invariants (pure, no I/O; ticket 05, ADR 0004).

These validate Team-scoped Label names and colours so services stay
declarative and the rules are unit-testable without a database.
"""

import re

from core.domain.errors import ValidationError

LABEL_NAME_MIN_LENGTH = 1
LABEL_NAME_MAX_LENGTH = 50
LABEL_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

MSG_LABEL_NAME_INVALID = "Label name must be 1-50 characters"
MSG_LABEL_COLOR_INVALID = "Label colour must be a 6-digit hex value (e.g. #f2c94c)"


def validate_label_name(name: str) -> str:
    """Trim and validate a Label name (1-50 chars).

    Args:
        name: The raw name as sent by the client.

    Returns:
        The trimmed name.

    Raises:
        ValidationError: If the trimmed name is shorter than 1 or longer
            than 50 characters.

    """
    stripped = name.strip()
    if not LABEL_NAME_MIN_LENGTH <= len(stripped) <= LABEL_NAME_MAX_LENGTH:
        raise ValidationError(MSG_LABEL_NAME_INVALID)
    return stripped


def validate_label_color(color: str) -> str:
    """Validate a Label colour (6-digit hex, ``#RRGGBB``).

    Args:
        color: The raw colour as sent by the client.

    Returns:
        The colour unchanged.

    Raises:
        ValidationError: If the colour is not a 6-digit hex value.

    """
    if not LABEL_COLOR_PATTERN.match(color):
        raise ValidationError(MSG_LABEL_COLOR_INVALID)
    return color
