"""Tests for the identifier helpers. No database required."""

import pytest
from core.domain.identifiers import format_identifier, is_valid_team_key, parse_identifier


@pytest.mark.parametrize("key", ["ENG", "AB", "ABCDE"])
def test_valid_team_keys(key: str) -> None:
    """Keys of 2-5 uppercase letters are valid."""
    assert is_valid_team_key(key) is True


@pytest.mark.parametrize("key", ["A", "ABCDEF", "eng", "EN1", "EN-G", ""])
def test_invalid_team_keys(key: str) -> None:
    """Anything else is rejected."""
    assert is_valid_team_key(key) is False


def test_format_and_parse_roundtrip() -> None:
    """Formatting then parsing returns the original parts."""
    assert format_identifier("ENG", 42) == "ENG-42"
    assert parse_identifier("ENG-42") == ("ENG", 42)
    assert parse_identifier(" eng-7 ") == ("ENG", 7)


def test_parse_rejects_garbage() -> None:
    """Malformed identifiers return None instead of raising."""
    assert parse_identifier("ENG") is None
    assert parse_identifier("42") is None
    assert parse_identifier("TOOLONG-1") is None
