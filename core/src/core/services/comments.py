"""Comment use-cases (brief §2, ticket 06): create, list, edit, delete."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.domain.comments import (
    CommentRef,
    can_delete_comment,
    can_edit_comment,
    validate_comment_body,
)
from core.domain.errors import ForbiddenError, NotFoundError
from core.models.activity import Activity
from core.models.comment import Comment
from core.models.issue import Issue
from core.models.team import Team
from core.models.user import User
from core.services.activity import record_activity
from core.services.actors import load_actor
from core.services.issues import MSG_TEAM_ARCHIVED, MSG_TEAM_NOT_FOUND, _visible_issue

ACTIVITY_COMMENT_CREATED = "comment.created"
ACTIVITY_COMMENT_UPDATED = "comment.updated"
ACTIVITY_COMMENT_DELETED = "comment.deleted"

MSG_COMMENT_NOT_FOUND = "Comment not found"
MSG_COMMENT_AUTHOR_ONLY = "Only the author can edit a Comment"
MSG_COMMENT_DELETE_FORBIDDEN = "Only the author, a Team owner, or an Admin can delete a Comment"

# Attributes refreshed after every write so the returned Comment carries the
# real server values, not naive defaults.
COMMENT_REFRESH_ATTRIBUTES: list[str] = ["author", "created_at"]


async def create_comment(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID, body: str
) -> Comment:
    """Create a Comment on an Issue (brief §2).

    Any Team member (or Admin) may comment. Emits one ``comment.created``
    Activity row.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        issue_id: The Issue the Comment belongs to.
        body: The Markdown body (1-20,000 chars, trimmed).

    Returns:
        The created Comment (author eager-loaded).

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor (non-members get 404, not 403).
        ForbiddenError: If the Issue's Team is archived.
        ValidationError: If the body is empty or too long.

    """
    body = validate_comment_body(body)
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        team = await _load_team(session, issue.team_id)
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        comment = Comment(issue_id=issue.id, author_id=actor.user_id, body=body)
        session.add(comment)
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_COMMENT_CREATED,
                comment_id=comment.id,
            ),
        )
        await session.flush()
        await session.refresh(comment, COMMENT_REFRESH_ATTRIBUTES)
        return comment


async def list_issue_comments(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID
) -> list[Comment]:
    """List an Issue's Comments, oldest first (full list, no pagination).

    Args:
        session: The database session.
        user: The authenticated acting user (Team member or Admin).
        issue_id: The Issue to list Comments for.

    Returns:
        The Issue's Comments in creation order, with the author eager-loaded.

    Raises:
        NotFoundError: If the Issue does not exist, is archived, or is not
            visible to the actor.

    """
    actor = await load_actor(session, user)
    issue = await _visible_issue(session, actor=actor, issue_id=issue_id)
    team = await _load_team(session, issue.team_id)
    if team.archived_at is not None:
        raise NotFoundError(MSG_TEAM_NOT_FOUND)
    comments = (
        await session.exec(
            select(Comment)
            .where(Comment.issue_id == issue.id)
            .options(joinedload(Comment.author))  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
            .order_by(Comment.created_at, Comment.id)  # type: ignore[attr-defined,arg-type]  # SQLModel fields are Columns at runtime
        )
    ).all()
    return list(comments)


async def update_comment(
    session: AsyncSession,
    *,
    user: User,
    issue_id: uuid.UUID,
    comment_id: uuid.UUID,
    body: str,
) -> Comment:
    """Edit a Comment's body (author only; repeatable, stamped with ``edited_at``).

    Comments are unversioned (ADR 0008 covers Issues and Workflow States
    only). Re-sending the same body is a no-op (no Activity, no new
    ``edited_at``). Emits one ``comment.updated`` Activity row per change.

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        issue_id: The Issue the Comment belongs to.
        comment_id: The Comment to edit.
        body: The new Markdown body (1-20,000 chars, trimmed).

    Returns:
        The updated Comment (author eager-loaded).

    Raises:
        NotFoundError: If the Issue or the Comment does not exist (a Comment
            of another Issue is invisible), or the Issue is archived/not
            visible to the actor.
        ForbiddenError: If the actor is not the author, or the Issue's Team
            is archived.
        ValidationError: If the body is empty or too long.

    """
    body = validate_comment_body(body)
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        team = await _load_team(session, issue.team_id)
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        comment = await _visible_comment(session, issue=issue, comment_id=comment_id)
        if not can_edit_comment(actor, _ref(issue, comment)):
            raise ForbiddenError(MSG_COMMENT_AUTHOR_ONLY)
        if comment.body == body:
            return comment
        comment.body = body
        comment.edited_at = datetime.now(UTC)
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_COMMENT_UPDATED,
                field="body",
                comment_id=comment.id,
            ),
        )
        await session.flush()
        await session.refresh(comment, COMMENT_REFRESH_ATTRIBUTES)
        return comment


async def delete_comment(
    session: AsyncSession, *, user: User, issue_id: uuid.UUID, comment_id: uuid.UUID
) -> None:
    """Delete a Comment (author, Team owner, or Admin).

    The row is removed outright (hard delete, no archive). Its
    ``comment.created``/``comment.updated`` Activity rows are removed and a
    single ``comment.deleted`` row is written, so the feed keeps a
    "deleted a Comment" trail (Linear-style).

    Args:
        session: The database session (the transaction is owned here).
        user: The authenticated acting user.
        issue_id: The Issue the Comment belongs to.
        comment_id: The Comment to delete.

    Raises:
        NotFoundError: If the Issue or the Comment does not exist (a Comment
            of another Issue is invisible), or the Issue is archived/not
            visible to the actor.
        ForbiddenError: If the actor may not delete the Comment, or the
            Issue's Team is archived.

    """
    async with session.begin():
        actor = await load_actor(session, user)
        issue = await _visible_issue(session, actor=actor, issue_id=issue_id, for_update=True)
        team = await _load_team(session, issue.team_id)
        if team.archived_at is not None:
            raise ForbiddenError(MSG_TEAM_ARCHIVED)
        comment = await _visible_comment(session, issue=issue, comment_id=comment_id)
        if not can_delete_comment(actor, _ref(issue, comment)):
            raise ForbiddenError(MSG_COMMENT_DELETE_FORBIDDEN)
        await session.exec(
            delete(Activity).where(
                Activity.comment_id == comment.id,  # type: ignore[arg-type]  # SQLModel field is a Column at runtime
                Activity.kind.in_([ACTIVITY_COMMENT_CREATED, ACTIVITY_COMMENT_UPDATED]),  # type: ignore[attr-defined]  # SQLModel field is a Column at runtime
            )
        )
        await session.delete(comment)
        record_activity(
            session,
            Activity(
                issue_id=issue.id,
                actor_id=actor.user_id,
                kind=ACTIVITY_COMMENT_DELETED,
                comment_id=comment.id,
            ),
        )
        await session.flush()


async def _load_team(session: AsyncSession, team_id: uuid.UUID) -> Team:
    """Load the Team of an Issue (for the archived check)."""
    return (await session.exec(select(Team).where(Team.id == team_id))).one()


async def _visible_comment(
    session: AsyncSession, *, issue: Issue, comment_id: uuid.UUID
) -> Comment:
    """Load a Comment scoped to the Issue (others are invisible, 404).

    Args:
        session: The database session (inside the caller's transaction).
        issue: The Issue the Comment must belong to.
        comment_id: The Comment to load.

    Returns:
        The Comment (author eager-loaded).

    Raises:
        NotFoundError: If no such Comment exists on the Issue.

    """
    comment = (
        await session.exec(
            select(Comment)
            .where(Comment.id == comment_id, Comment.issue_id == issue.id)
            .options(joinedload(Comment.author))  # type: ignore[arg-type,attr-defined]  # Relationship attrs are Columns at runtime
        )
    ).one_or_none()
    if comment is None:
        raise NotFoundError(MSG_COMMENT_NOT_FOUND)
    return comment


def _ref(issue: Issue, comment: Comment) -> CommentRef:
    """Build the plain-data Comment ref for the domain authorization checks."""
    return CommentRef(team_id=issue.team_id, author_id=comment.author_id)
