"""Search rules (pure, no I/O; ticket 09, ADR 0004).

Query cleaning and the result cap for the global Issue search.
"""

from core.domain.errors import ValidationError
from core.domain.listing import DEFAULT_LIMIT

MSG_SEARCH_QUERY_REQUIRED = "Search query is required"

# Fixed result cap: a search is one page (no cursor). It is the list's
# default page size so the two cannot silently diverge (ticket 09).
SEARCH_RESULT_LIMIT = DEFAULT_LIMIT


def clean_search_query(raw: str | None) -> str:
    """Trim the raw search query; empty after trimming is invalid.

    Args:
        raw: The raw query from the request (or ``None`` when absent).

    Returns:
        The trimmed, non-empty query.

    Raises:
        ValidationError: If the query is missing or blank.

    """
    query = (raw or "").strip()
    if not query:
        raise ValidationError(MSG_SEARCH_QUERY_REQUIRED)
    return query
