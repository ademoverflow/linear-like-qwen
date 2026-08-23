import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import UUID, Column, DateTime, Integer, Text, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.issue import Issue
    from core.models.membership import Membership
    from core.models.workflow import Workflow


class Team(SQLModel, table=True):
    """Model Class Team (brief §2: unit of ownership)."""

    __tablename__: ClassVar[str] = "teams"

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
    name: str = Field(max_length=100, nullable=False)
    key: str = Field(max_length=5, unique=True, nullable=False)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    archived_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    # Per-Team Issue number counter (ADR 0010): allocated under
    # SELECT ... FOR UPDATE, never reused.
    next_issue_number: int = Field(
        default=1,
        sa_column=Column(Integer, server_default=text("1"), nullable=False),
    )

    workflow: "Workflow" = Relationship(
        back_populates="team",
        sa_relationship_kwargs={"uselist": False},
    )
    issues: list["Issue"] = Relationship(back_populates="team")
    memberships: list["Membership"] = Relationship(back_populates="team")
