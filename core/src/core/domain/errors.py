"""Domain error hierarchy.

Services raise these; a single FastAPI exception handler (see ``core.main``) maps them to
HTTP status codes and the ``{"error": {...}}`` envelope. Routers never build error
responses by hand.
"""

from typing import Any


class DomainError(Exception):
    """Base class for all domain errors."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        """Create a domain error.

        Args:
            message: Human-readable message, safe to show to the client.
            details: Optional structured context (field names, ids, ...).

        """
        super().__init__(message)
        self.message = message
        self.details = details

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the API error envelope."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}


class ValidationError(DomainError):
    """Input is well-formed but semantically invalid (400)."""

    status_code = 400
    code = "validation_error"


class ForbiddenError(DomainError):
    """The actor is not allowed to perform this action (403)."""

    status_code = 403
    code = "forbidden"


class NotFoundError(DomainError):
    """The resource does not exist or is not visible to the actor (404)."""

    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    """Stale update or uniqueness clash (409)."""

    status_code = 409
    code = "conflict"


class RuleViolationError(DomainError):
    """A domain invariant would be broken, e.g. workflow category minimums (422)."""

    status_code = 422
    code = "rule_violation"


class AuthenticationError(DomainError):
    """Credentials are invalid (401).

    Used by ``POST /auth/login``; the auth dependency keeps FastAPI's native 401.
    """

    status_code = 401
    code = "unauthenticated"


class RateLimitError(DomainError):
    """Too many attempts in the window (429, ADR 0009)."""

    status_code = 429
    code = "rate_limited"
