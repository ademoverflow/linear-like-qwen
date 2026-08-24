"""Issue input invariants (pure, no I/O; brief §3, ADR 0004).

These validate the editable Issue fields (brief §3.1) and the bulk
operation rules (brief §4.4) so services stay declarative and the rules
are unit-testable without a database.
"""

import uuid
from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# Hard delete (brief §3.4, ticket 07)
# ---------------------------------------------------------------------------

MSG_IDENTIFIER_MISMATCH = "The entered identifier does not match the Issue"


def confirm_identifier(expected: str, provided: str) -> None:
    """Confirm a hard delete by repeating the Issue's identifier.

    The client must send the exact canonical identifier (e.g. ``ENG-42``)
    in the DELETE body; surrounding whitespace is tolerated, any other
    difference is a 400 before anything is deleted.

    Args:
        expected: The Issue's canonical identifier (``KEY-number``).
        provided: The identifier the client repeated as confirmation.

    Raises:
        ValidationError: If the trimmed input does not exactly match
            ``expected`` (case-sensitive).

    """
    if provided.strip() != expected:
        raise ValidationError(MSG_IDENTIFIER_MISMATCH)


# ---------------------------------------------------------------------------
# Bulk operations (brief §4.4, ticket 05)
# ---------------------------------------------------------------------------

MSG_BULK_NO_ACTION = "A bulk operation needs exactly one action"
MSG_BULK_MULTI_ACTION = "A bulk operation accepts only one action"


@dataclass(frozen=True)
class BulkAction:
    """The single action of a bulk operation (exactly one field set)."""

    state_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    add_label_ids: tuple[uuid.UUID, ...] = ()
    remove_label_ids: tuple[uuid.UUID, ...] = ()
    archive: bool = False


def parse_bulk_action(
    *,
    state_id: uuid.UUID | None,
    assignee_id: uuid.UUID | None,
    add_label_ids: tuple[uuid.UUID, ...],
    remove_label_ids: tuple[uuid.UUID, ...],
    archive: bool,
) -> BulkAction:
    """Validate that a bulk request carries exactly one action.

    Args:
        state_id: Target State id (the transition action).
        assignee_id: Target assignee id (the assign action).
        add_label_ids: Label ids to attach (the add-labels action).
        remove_label_ids: Label ids to detach (the remove-labels action).
        archive: Whether the action is archiving (must be ``True`` to
            count as the archive action).

    Returns:
        The parsed action.

    Raises:
        ValidationError: If zero or several actions are given.

    """
    actions = [
        state_id is not None,
        assignee_id is not None,
        len(add_label_ids) > 0,
        len(remove_label_ids) > 0,
        archive,
    ]
    if not any(actions):
        raise ValidationError(MSG_BULK_NO_ACTION)
    if sum(actions) > 1:
        raise ValidationError(MSG_BULK_MULTI_ACTION)
    return BulkAction(
        state_id=state_id,
        assignee_id=assignee_id,
        add_label_ids=add_label_ids,
        remove_label_ids=remove_label_ids,
        archive=archive,
    )
