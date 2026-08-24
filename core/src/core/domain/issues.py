"""Issue input invariants (pure, no I/O; brief §3, ADR 0004).

These validate the editable Issue fields (brief §3.1) so services stay
declarative and the rules are unit-testable without a database.
"""

from core.domain.errors import ValidationError

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 50_000
ESTIMATE_MIN = 0
ESTIMATE_MAX = 21
PRIORITIES: tuple[str, ...] = ("none", "urgent", "high", "medium", "low")

MSG_TITLE_INVALID = "Title must be 1-255 characters"
MSG_DESCRIPTION_INVALID = "Description must be at most 50,000 characters"
MSG_PRIORITY_INVALID = "Priority must be one of: none, urgent, high, medium, low"
MSG_ESTIMATE_INVALID = "Estimate must be between 0 and 21"


def validate_title(title: str) -> str:
    """Trim and validate an Issue title (1-255 chars).

    Args:
        title: The raw title as sent by the client.

    Returns:
        The trimmed title.

    Raises:
        ValidationError: If the trimmed title is shorter than 1 or longer
            than 255 characters.

    """
    stripped = title.strip()
    if not TITLE_MIN_LENGTH <= len(stripped) <= TITLE_MAX_LENGTH:
        raise ValidationError(MSG_TITLE_INVALID)
    return stripped


def validate_description(description: str | None) -> str | None:
    """Validate the Markdown description (optional, at most 50,000 chars).

    Args:
        description: The raw description as sent by the client.

    Returns:
        The description unchanged (``None`` stays ``None``).

    Raises:
        ValidationError: If the description is longer than 50,000 characters.

    """
    if description is not None and len(description) > DESCRIPTION_MAX_LENGTH:
        raise ValidationError(MSG_DESCRIPTION_INVALID)
    return description


def validate_priority(priority: str) -> str:
    """Validate a priority value (brief §3.1).

    Args:
        priority: The raw priority as sent by the client.

    Returns:
        The priority unchanged.

    Raises:
        ValidationError: If the value is not one of none/urgent/high/medium/low.

    """
    if priority not in PRIORITIES:
        raise ValidationError(MSG_PRIORITY_INVALID)
    return priority


def validate_estimate(estimate: int | None) -> int | None:
    """Validate the estimate (optional, 0-21, brief §3.1).

    Args:
        estimate: The raw estimate as sent by the client.

    Returns:
        The estimate unchanged (``None`` stays ``None``).

    Raises:
        ValidationError: If the estimate is outside 0-21.

    """
    if estimate is not None and not ESTIMATE_MIN <= estimate <= ESTIMATE_MAX:
        raise ValidationError(MSG_ESTIMATE_INVALID)
    return estimate
