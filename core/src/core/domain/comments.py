"""Comment rules (pure, no I/O; brief §2, ticket 06, ADR 0004).

Comment body validation and the edit/delete authorization rules, unit-tested
without a database. Editing is author-only; deletion is author, Team owner or
workspace Admin (brief §2) — a composite rule, so it lives here rather than in
the single-action ``can()`` matrix (recorded in the ticket).
"""

import uuid
from dataclasses import dataclass

from core.domain.authz import Actor, Role
from core.domain.errors import ValidationError

COMMENT_BODY_MIN_LENGTH = 1
# The Issue description allows 50,000 (brief §3.1); Comments get a tighter cap.
COMMENT_BODY_MAX_LENGTH = 20_000

MSG_COMMENT_BODY_EMPTY = "Comment body must not be empty"
MSG_COMMENT_BODY_TOO_LONG = "Comment body must be at most 20,000 characters"


@dataclass(frozen=True)
class CommentRef:
    """A Comment as plain data for the authorization checks (no I/O)."""

    team_id: uuid.UUID
    author_id: uuid.UUID


def validate_comment_body(body: str) -> str:
    """Trim and validate a Comment body (1-20,000 chars).

    Args:
        body: The raw Markdown body as sent by the client.

    Returns:
        The trimmed body.

    Raises:
        ValidationError: If the trimmed body is empty or longer than 20,000
            characters.

    """
    stripped = body.strip()
    if len(stripped) < COMMENT_BODY_MIN_LENGTH:
        raise ValidationError(MSG_COMMENT_BODY_EMPTY)
    if len(stripped) > COMMENT_BODY_MAX_LENGTH:
        raise ValidationError(MSG_COMMENT_BODY_TOO_LONG)
    return stripped


def can_edit_comment(actor: Actor, comment: CommentRef) -> bool:
    """Decide whether ``actor`` may edit the Comment (author only).

    Args:
        actor: The principal acting.
        comment: The Comment to edit (Team + author).

    Returns:
        True only when the actor is the Comment's author (no owner or Admin
        exception; brief §2).

    """
    return actor.user_id == comment.author_id


def can_delete_comment(actor: Actor, comment: CommentRef) -> bool:
    """Decide whether ``actor`` may delete the Comment.

    The author, a Team owner, or a workspace Admin may delete (brief §2).
    Non-members never reach this check (they get 404 on the Issue).

    Args:
        actor: The principal acting.
        comment: The Comment to delete (Team + author).

    Returns:
        True if the actor may delete the Comment.

    """
    if actor.user_id == comment.author_id:
        return True
    if actor.is_admin:
        return True
    return actor.team_roles.get(comment.team_id) is Role.OWNER
