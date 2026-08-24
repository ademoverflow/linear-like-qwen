"""Tests for Issue listing rules (sort, limit, cursor). No database required."""

import uuid
from datetime import UTC, datetime

import pytest
from core.domain.errors import ValidationError
from core.domain.listing import (
    PRIORITY_RANK,
    CursorIssue,
    SortSpec,
    cursor_sort_value,
    decode_cursor,
    encode_cursor,
    parse_sort,
    validate_cursor_for_sort,
    validate_limit,
    validate_priorities,
)

ISSUE_ID = uuid.uuid4()
NOW = datetime(2026, 8, 24, 12, 0, 0, 123456, tzinfo=UTC)


def _issue(priority: str = "none") -> CursorIssue:
    return CursorIssue(created_at=NOW, updated_at=NOW, priority=priority)


def test_parse_sort_default() -> None:
    """No sort input means created, newest first."""
    assert parse_sort(None) == SortSpec(key="created", direction="desc")


def test_parse_sort_valid_values() -> None:
    """Every key/direction combination parses."""
    assert parse_sort("created:asc") == SortSpec(key="created", direction="asc")
    assert parse_sort("updated:desc") == SortSpec(key="updated", direction="desc")
    assert parse_sort("priority:asc") == SortSpec(key="priority", direction="asc")


@pytest.mark.parametrize(
    "sort",
    ["number:desc", "created:up", "created", "created:desc:extra", "", "CREATED:DESC"],
)
def test_parse_sort_rejects_bad_values(sort: str) -> None:
    """Unknown keys, directions or shapes are rejected (400)."""
    with pytest.raises(ValidationError, match="Sort must be"):
        parse_sort(sort)


def test_priority_rank_ordering() -> None:
    """Urgent outranks high, which outranks medium, low and none."""
    assert PRIORITY_RANK["urgent"] > PRIORITY_RANK["high"]
    assert PRIORITY_RANK["high"] > PRIORITY_RANK["medium"]
    assert PRIORITY_RANK["medium"] > PRIORITY_RANK["low"]
    assert PRIORITY_RANK["low"] > PRIORITY_RANK["none"]


def test_validate_limit_default_and_bounds() -> None:
    """Default is 50; 1 and 200 are allowed."""
    assert validate_limit(None) == 50
    assert validate_limit(1) == 1
    assert validate_limit(200) == 200


@pytest.mark.parametrize("limit", [0, -1, 201, 1000])
def test_validate_limit_rejects_out_of_range(limit: int) -> None:
    """Limits outside 1-200 are rejected (400)."""
    with pytest.raises(ValidationError, match="between 1 and 200"):
        validate_limit(limit)


def test_validate_priorities() -> None:
    """Known priorities pass; unknown values are rejected (400)."""
    assert validate_priorities(("urgent", "none")) == ("urgent", "none")
    with pytest.raises(ValidationError, match="Priority must be one of"):
        validate_priorities(("urgent", "blocker"))


def test_cursor_round_trip_created() -> None:
    """A created-cursor encodes and decodes to the same values."""
    spec = SortSpec(key="created", direction="desc")
    token = encode_cursor(spec, NOW.isoformat(), 42, ISSUE_ID)
    cursor = decode_cursor(token)
    assert cursor.key == "created"
    assert cursor.value == NOW.isoformat()
    assert cursor.number == 42
    assert cursor.id == ISSUE_ID


def test_cursor_round_trip_priority() -> None:
    """A priority cursor stores the rank, not the priority name."""
    spec = SortSpec(key="priority", direction="desc")
    token = encode_cursor(spec, PRIORITY_RANK["urgent"], 7, ISSUE_ID)
    cursor = decode_cursor(token)
    assert cursor.value == PRIORITY_RANK["urgent"]


def test_cursor_sort_value_uses_priority_rank() -> None:
    """cursor_sort_value maps the priority to its rank and the timestamp to ISO."""
    assert cursor_sort_value(SortSpec("priority", "asc"), _issue("urgent")) == 4
    assert cursor_sort_value(SortSpec("created", "desc"), _issue()) == NOW.isoformat()
    assert cursor_sort_value(SortSpec("updated", "asc"), _issue()) == NOW.isoformat()


@pytest.mark.parametrize("token", ["!!!not-base64!!!", "YWJj", "e30="])
def test_cursor_rejects_garbage(token: str) -> None:
    """Malformed tokens are rejected (400)."""
    with pytest.raises(ValidationError, match="Invalid cursor"):
        decode_cursor(token)


def test_cursor_matches_its_sort() -> None:
    """A cursor from the same sort key passes the check."""
    sort = SortSpec(key="created", direction="desc")
    cursor = decode_cursor(encode_cursor(sort, "2026-01-01T00:00:00+00:00", 1, ISSUE_ID))
    validate_cursor_for_sort(cursor, sort)  # does not raise


@pytest.mark.parametrize(
    ("cursor_key", "sort_key"),
    [
        ("created", "priority"),
        ("priority", "created"),
        ("updated", "priority"),
    ],
)
def test_cursor_from_other_sort_is_rejected(cursor_key: str, sort_key: str) -> None:
    """Mixing a cursor with another sort key is a 400, not a type error."""
    value = "2026-01-01T00:00:00+00:00" if cursor_key != "priority" else 4
    cursor = decode_cursor(
        encode_cursor(SortSpec(key=cursor_key, direction="desc"), value, 1, ISSUE_ID)
    )
    with pytest.raises(ValidationError):
        validate_cursor_for_sort(cursor, SortSpec(key=sort_key, direction="desc"))
