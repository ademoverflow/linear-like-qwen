"""Team keys and Issue identifiers."""

import re
from typing import Final

TEAM_KEY_PATTERN: Final = re.compile(r"^[A-Z]{2,5}$")


def is_valid_team_key(key: str) -> bool:
    """Return True if ``key`` is 2-5 uppercase ASCII letters."""
    return TEAM_KEY_PATTERN.fullmatch(key) is not None


def format_identifier(team_key: str, number: int) -> str:
    """Build the human identifier for an Issue, e.g. ``ENG-42``."""
    return f"{team_key}-{number}"


def parse_identifier(identifier: str) -> tuple[str, int] | None:
    """Split ``ENG-42`` into ``("ENG", 42)``; return None if malformed."""
    match = re.fullmatch(r"([A-Z]{2,5})-(\d+)", identifier.strip().upper())
    if match is None:
        return None
    return match.group(1), int(match.group(2))
