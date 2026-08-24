"""Comments router (thin): the Issue-scoped comment thread (ticket 06, brief §9)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from core.database import get_session
from core.middlewares.user import get_current_user
from core.models.comment import Comment
from core.models.user import User
from core.services import comments as comments_service

router = APIRouter(prefix="/issues/{issue_id}/comments", tags=["Comments"])


class CommentBodyRequest(BaseModel):
    """Body for ``POST /issues/{issue_id}/comments`` and ``PATCH .../{comment_id}``.

    ``min_length=1`` rejects the empty string (422, like the Issue title); the
    20,000-char cap is enforced by the domain *after* trimming, so a body that
    trims to a valid length is accepted.
    """

    body: str = Field(min_length=1)


class CommentResponse(BaseModel):
    """A Comment as exposed by the API (author display-ready)."""

    id: uuid.UUID
    issue_id: uuid.UUID
    author_id: uuid.UUID
    author_display_name: str | None
    author_avatar_url: str | None
    body: str
    created_at: datetime
    edited_at: datetime | None


def comment_response(comment: Comment) -> CommentResponse:
    """Build a CommentResponse from a Comment (author eager-loaded)."""
    return CommentResponse(
        id=comment.id,
        issue_id=comment.issue_id,
        author_id=comment.author_id,
        author_display_name=comment.author.display_name if comment.author else None,
        author_avatar_url=comment.author.avatar_url if comment.author else None,
        body=comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


@router.get("")
async def list_issue_comments(
    issue_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CommentResponse]:
    """List an Issue's Comments, oldest first (Team member or Admin; 404 otherwise)."""
    comments = await comments_service.list_issue_comments(session, user=user, issue_id=issue_id)
    return [comment_response(comment) for comment in comments]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_comment(
    issue_id: uuid.UUID,
    payload: CommentBodyRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommentResponse:
    """Create a Comment (any Team member or Admin; 403 on an archived Team)."""
    comment = await comments_service.create_comment(
        session, user=user, issue_id=issue_id, body=payload.body
    )
    return comment_response(comment)


@router.patch("/{comment_id}")
async def update_comment(
    issue_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentBodyRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommentResponse:
    """Edit a Comment's body (author only; 403 for other authors)."""
    comment = await comments_service.update_comment(
        session, user=user, issue_id=issue_id, comment_id=comment_id, body=payload.body
    )
    return comment_response(comment)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    issue_id: uuid.UUID,
    comment_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a Comment (author, Team owner, or Admin; 403 otherwise)."""
    await comments_service.delete_comment(
        session, user=user, issue_id=issue_id, comment_id=comment_id
    )
