"""Tests for the search query rules (ticket 09, pure, no DB)."""

import pytest
from core.domain.errors import ValidationError
from core.domain.search import SEARCH_RESULT_LIMIT, clean_search_query


def test_clean_search_query_trims_whitespace() -> None:
    """The raw query is trimmed before matching."""
    assert clean_search_query("  eng-1  ") == "eng-1"


def test_clean_search_query_accepts_single_char() -> None:
    """A one-character query is valid (substring search)."""
    assert clean_search_query("x") == "x"


def test_clean_search_query_rejects_missing() -> None:
    """A missing query is a 400."""
    with pytest.raises(ValidationError, match="Search query is required"):
        clean_search_query(None)


def test_clean_search_query_rejects_empty() -> None:
    """An empty query is a 400."""
    with pytest.raises(ValidationError, match="Search query is required"):
        clean_search_query("")


def test_clean_search_query_rejects_blank() -> None:
    """A whitespace-only query is a 400."""
    with pytest.raises(ValidationError, match="Search query is required"):
        clean_search_query("   ")


def test_search_result_limit_is_the_default_page_size() -> None:
    """The cap is a single page of the list's default size (no cursor)."""
    assert SEARCH_RESULT_LIMIT == 50
