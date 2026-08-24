"""Unit tests for the pure Comment rules (ticket 06). No database required."""

import uuid

import pytest
from core.domain.authz import Actor, Role
from core.domain.comments import (
    COMMENT_BODY_MAX_LENGTH,
    CommentRef,
    can_delete_comment,
    can_edit_comment,
    validate_comment_body,
)
from core.domain.errors import ValidationError

TEAM_A = uuid.uuid4()


def _actor(
    user_id: uuid.UUID | None = None,
    *,
    is_admin: bool = False,
    roles: dict[uuid.UUID, Role] | None = None,
) -> Actor:
    return Actor(user_id=user_id or uuid.uuid4(), is_admin=is_admin, team_roles=roles or {})


def test_body_is_trimmed_and_returned() -> None:
    """Surrounding whitespace is stripped (like the Issue title)."""
    assert validate_comment_body("  hello  ") == "hello"


def test_empty_body_is_rejected() -> None:
    """A Comment needs a non-empty body after trimming."""
    with pytest.raises(ValidationError):
        validate_comment_body("")
    with pytest.raises(ValidationError):
        validate_comment_body("   \n\t")


def test_oversized_body_is_rejected() -> None:
    """The body cap is 20,000 characters (the Issue description allows 50,000)."""
    with pytest.raises(ValidationError):
        validate_comment_body("x" * (COMMENT_BODY_MAX_LENGTH + 1))
    assert validate_comment_body("x" * COMMENT_BODY_MAX_LENGTH) == "x" * COMMENT_BODY_MAX_LENGTH


def test_only_the_author_can_edit() -> None:
    """Editing is author-only: no owner or Admin exception (brief §2)."""
    author = uuid.uuid4()
    comment = CommentRef(team_id=TEAM_A, author_id=author)

    assert can_edit_comment(_actor(user_id=author, roles={TEAM_A: Role.MEMBER}), comment) is True
    assert can_edit_comment(_actor(roles={TEAM_A: Role.OWNER}), comment) is False
    assert can_edit_comment(_actor(is_admin=True), comment) is False
    assert can_edit_comment(_actor(roles={TEAM_A: Role.MEMBER}), comment) is False


def test_delete_by_author_owner_or_admin() -> None:
    """Deletion: the author, a Team owner, or a workspace Admin (brief §2)."""
    author = uuid.uuid4()
    comment = CommentRef(team_id=TEAM_A, author_id=author)

    assert can_delete_comment(_actor(user_id=author, roles={TEAM_A: Role.MEMBER}), comment) is True
    assert can_delete_comment(_actor(roles={TEAM_A: Role.OWNER}), comment) is True
    assert can_delete_comment(_actor(is_admin=True, roles={}), comment) is True
    assert can_delete_comment(_actor(roles={TEAM_A: Role.MEMBER}), comment) is False
    assert can_delete_comment(_actor(roles={}), comment) is False
    assert can_delete_comment(_actor(roles={uuid.uuid4(): Role.OWNER}), comment) is False
