"""Issue listing rules (pure, no I/O; ticket 05, ADR 0004).

Sort, limit and cursor invariants for the paginated Issue list. All
functions are pure so the rules are unit-testable without a database.
"""

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from core.domain.errors import ValidationError
from core.domain.issues import PRIORITIES

SORT_KEYS: tuple[str, ...] = ("created", "updated", "priority")
SORT_DIRECTIONS: tuple[str, ...] = ("asc", "desc")

# Highest priority first (brief §3.1: urgent > high > medium > low > none).
PRIORITY_RANK: dict[str, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
}

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
SORT_PART_COUNT = 2

MSG_SORT_INVALID = "Sort must be one of created/updated/priority with :asc or :desc"
MSG_LIMIT_INVALID = "Limit must be between 1 and 200"
MSG_CURSOR_INVALID = "Invalid cursor"
MSG_PRIORITY_INVALID = "Priority must be one of: none, urgent, high, medium, low"
MSG_CURSOR_SORT_MISMATCH = "Cursor does not match the requested sort"


@dataclass(frozen=True)
class SortSpec:
    """A parsed sort (key plus direction)."""

    key: str
    direction: str


@dataclass(frozen=True)
class Cursor:
    """A decoded pagination cursor: the last row of the previous page.

    ``value`` is the row's sort value (an ISO timestamp for created/updated,
    a priority rank for priority); ``number`` is the Issue number
    (tie-breaker); ``id`` disambiguates rows sharing both.
    """

    key: str
    value: str | int
    number: int
    id: uuid.UUID


def parse_sort(sort: str | None) -> SortSpec:
    """Parse ``created:desc``-style sort input (default ``created:desc``).

    Args:
        sort: The raw sort string, or ``None`` for the default.

    Returns:
        The parsed sort.

    Raises:
        ValidationError: If the key or direction is unknown.

    """
    if sort is None:
        return SortSpec(key="created", direction="desc")
    parts = sort.split(":")
    if (
        len(parts) != SORT_PART_COUNT
        or parts[0] not in SORT_KEYS
        or parts[1] not in SORT_DIRECTIONS
    ):
        raise ValidationError(MSG_SORT_INVALID)
    return SortSpec(key=parts[0], direction=parts[1])


def validate_limit(limit: int | None) -> int:
    """Validate the page size (default 50, max 200).

    Args:
        limit: The raw limit, or ``None`` for the default.

    Returns:
        The page size to use.

    Raises:
        ValidationError: If the limit is outside 1-200.

    """
    if limit is None:
        return DEFAULT_LIMIT
    if not 1 <= limit <= MAX_LIMIT:
        raise ValidationError(MSG_LIMIT_INVALID)
    return limit


def validate_priorities(priorities: tuple[str, ...]) -> tuple[str, ...]:
    """Validate a set of priority filter values.

    Args:
        priorities: The raw priorities from the request.

    Returns:
        The priorities unchanged.

    Raises:
        ValidationError: If any value is not a known priority.

    """
    for priority in priorities:
        if priority not in PRIORITIES:
            raise ValidationError(MSG_PRIORITY_INVALID)
    return priorities


def encode_cursor(sort: SortSpec, value: str | int, number: int, issue_id: uuid.UUID) -> str:
    """Encode a pagination cursor as an opaque base64 token.

    Args:
        sort: The sort the cursor belongs to.
        value: The last row's sort value.
        number: The last row's Issue number.
        issue_id: The last row's Issue id.

    Returns:
        The opaque cursor token.

    """
    payload = json.dumps({"key": sort.key, "value": value, "number": number, "id": str(issue_id)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> Cursor:
    """Decode a pagination token.

    Args:
        cursor: The opaque cursor token from the client.

    Returns:
        The decoded cursor.

    Raises:
        ValidationError: If the token is malformed.

    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
        return Cursor(
            key=payload["key"],
            value=cast("str | int", payload["value"]),
            number=int(payload["number"]),
            id=uuid.UUID(str(payload["id"])),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError(MSG_CURSOR_INVALID) from exc


def validate_cursor_for_sort(cursor: Cursor, sort: SortSpec) -> None:
    """Ensure a cursor was encoded with the sort it is being used with.

    Args:
        cursor: The decoded pagination token.
        sort: The sort requested with the current page.

    Raises:
        ValidationError: If the cursor belongs to a different sort key
            (mixing them would compare incompatible sort values).

    """
    if cursor.key != sort.key:
        raise ValidationError(MSG_CURSOR_SORT_MISMATCH)


def cursor_sort_value(sort: SortSpec, issue: "CursorIssue") -> str | int:
    """Extract the sort value of an Issue for cursor encoding.

    Args:
        sort: The sort in use.
        issue: The last row of the page (plain values, no ORM).

    Returns:
        The sort value to store in the cursor.

    """
    if sort.key == "created":
        return issue.created_at.isoformat()
    if sort.key == "updated":
        return issue.updated_at.isoformat()
    return PRIORITY_RANK[issue.priority]


@dataclass(frozen=True)
class CursorIssue:
    """The plain values a cursor is built from (no ORM)."""

    created_at: datetime
    updated_at: datetime
    priority: str


@dataclass(frozen=True)
class IssueQuery:
    """A parsed and validated Issue list request (brief §9).

    Built by the router from the raw query params (via the pure validators
    in this module) and consumed by the service layer.
    """

    state_ids: tuple[uuid.UUID, ...] = ()
    assignee_ids: tuple[uuid.UUID, ...] = ()
    label_ids: tuple[uuid.UUID, ...] = ()
    priorities: tuple[str, ...] = ()
    sort: SortSpec = SortSpec(key="created", direction="desc")
    cursor: Cursor | None = None
    limit: int = DEFAULT_LIMIT
    include_archived: bool = False
