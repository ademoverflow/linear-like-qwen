import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar, Optional

from sqlalchemy import UUID, Column, DateTime, ForeignKey, Index, Text, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.issue import Issue
    from core.models.user import User


class Comment(SQLModel, table=True):
    """Model Class Comment (brief §2: Markdown body on an Issue by a User).

    ``issue_id`` is ``ON DELETE CASCADE`` so a hard-deleted Issue (ticket 07)
    removes its Comments without extra code. The author FK is plain: v1 never
    hard-deletes Users (deactivation only, brief §5.2).
    """

    __tablename__: ClassVar[str] = "comments"
    __table_args__ = (
        Index("ix_comments_issue_id", "issue_id"),
        Index("ix_comments_author_id", "author_id"),
    )

    id: uuid.UUID = Field(
        sa_column=Column(
            UUID,
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        default_factory=uuid.uuid4,
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("now()"),
            nullable=False,
        ),
        default_factory=datetime.now,
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("now()"),
            onupdate=text("now()"),
            nullable=False,
        ),
        default_factory=datetime.now,
    )
    issue_id: uuid.UUID = Field(
        sa_column=Column(UUID, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    )
    author_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    body: str = Field(sa_column=Column(Text, nullable=False))
    edited_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    issue: "Issue" = Relationship()
    author: Optional["User"] = Relationship(
        sa_relationship_kwargs={"primaryjoin": "Comment.author_id == User.id"}
    )
