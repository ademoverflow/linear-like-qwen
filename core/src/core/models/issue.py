import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, ClassVar, Optional

from sqlalchemy import UUID, Column, Date, DateTime, Integer, Text, text
from sqlmodel import Field, Index, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.team import Team
    from core.models.user import User
    from core.models.workflow_state import WorkflowState


class Issue(SQLModel, table=True):
    """Model Class Issue (brief §3).

    The human identifier (``KEY-number``) is computed from the Team key and
    ``number``; it is never stored.
    """

    __tablename__: ClassVar[str] = "issues"
    __table_args__ = (Index("uq_issues_team_number", "team_id", "number", unique=True),)

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
    team_id: uuid.UUID = Field(foreign_key="teams.id", nullable=False)
    number: int = Field(nullable=False)
    title: str = Field(max_length=255, nullable=False)
    description: str | None = Field(
        default=None, max_length=50_000, sa_column=Column(Text, nullable=True)
    )
    state_id: uuid.UUID = Field(foreign_key="workflow_states.id", nullable=False)
    # "none" | "urgent" | "high" | "medium" | "low".
    priority: str = Field(
        max_length=10, nullable=False, sa_column_kwargs={"server_default": text("'none'")}
    )
    assignee_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    creator_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="issues.id")
    due_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    estimate: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    canceled_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    archived_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    team: "Team" = Relationship(back_populates="issues")
    state: "WorkflowState" = Relationship()
    assignee: Optional["User"] = Relationship(
        sa_relationship_kwargs={"primaryjoin": "Issue.assignee_id == User.id"}
    )
    creator: "User" = Relationship(
        sa_relationship_kwargs={"primaryjoin": "Issue.creator_id == User.id"}
    )
