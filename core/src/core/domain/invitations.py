"""Invitation token rules (pure, no I/O; ADR 0012).

The random token is what the Admin shares with the invitee; only its
SHA-256 hex digest is stored at rest, so a leaked database row does not
leak usable tokens.
"""

import hashlib
import secrets
from datetime import datetime
from typing import Literal

InvitationState = Literal["valid", "expired", "used"]

# Entropy of the raw token (token_urlsafe of 32 bytes).
TOKEN_BYTES = 32


def generate_token() -> str:
    """Generate a random URL-safe token (shared with the invitee)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Hash a token to its SHA-256 hex digest (stored at rest)."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def invitation_state(
    *, expires_at: datetime, accepted_at: datetime | None, now: datetime
) -> InvitationState:
    """Classify an Invitation as ``used``, ``expired`` or ``valid``.

    An accepted Invitation reports ``used`` even after its expiry, so the
    register flow can give a precise, stable rejection message.

    Args:
        expires_at: When the Invitation stops being usable.
        accepted_at: Set once the invitee registered (never ``None`` after).
        now: The current instant (passed in, so the rule stays testable).

    Returns:
        The Invitation's state.

    """
    if accepted_at is not None:
        return "used"
    if expires_at < now:
        return "expired"
    return "valid"
