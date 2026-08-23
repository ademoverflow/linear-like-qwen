"""Unit tests for Invitation token rules (no DB; spec seam 1, ADR 0012)."""

import hashlib
from datetime import UTC, datetime, timedelta

from core.domain.invitations import generate_token, hash_token, invitation_state

NOW = datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)


def test_generate_token_is_unique_and_urlsafe() -> None:
    """Tokens are random and safe to share in a URL or the UI."""
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100
    for token in tokens:
        assert token.isascii()
        assert all(char.isalnum() or char in "-_" for char in token)


def test_hash_token_is_sha256_hex() -> None:
    """The stored form is the SHA-256 hex digest of the token."""
    token = generate_token()
    assert hash_token(token) == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_invitation_state_valid() -> None:
    """An unaccepted Invitation before its expiry is valid."""
    assert (
        invitation_state(expires_at=NOW + timedelta(days=7), accepted_at=None, now=NOW) == "valid"
    )


def test_invitation_state_expired() -> None:
    """An unaccepted Invitation past its expiry is expired."""
    assert (
        invitation_state(expires_at=NOW - timedelta(seconds=1), accepted_at=None, now=NOW)
        == "expired"
    )


def test_invitation_state_used_wins_over_expiry() -> None:
    """An accepted Invitation reports used even after its expiry."""
    assert (
        invitation_state(
            expires_at=NOW - timedelta(days=1),
            accepted_at=NOW - timedelta(days=2),
            now=NOW,
        )
        == "used"
    )
