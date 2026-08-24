import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, Index, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.team import Team


class Label(SQLModel, table=True):
    """Model Class Label (brief §2: Team-scoped tag on Issues)."""

    __tablename__: ClassVar[str] = "labels"
    __table_args__ = (Index("uq_labels_team_name", "team_id", "name", unique=True),)

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
    name: str = Field(max_length=50, nullable=False)
    color: str = Field(max_length=7, nullable=False)

    team: "Team" = Relationship(back_populates="labels")
