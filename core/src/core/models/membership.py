import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, Index, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.team import Team
    from core.models.user import User


class Membership(SQLModel, table=True):
    """Model Class Membership (User ↔ Team, brief §2)."""

    __tablename__: ClassVar[str] = "memberships"
    __table_args__ = (Index("uq_memberships_user_team", "user_id", "team_id", unique=True),)

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
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False)
    team_id: uuid.UUID = Field(foreign_key="teams.id", nullable=False)
    # "owner" or "member" (core.domain.authz.Role).
    role: str = Field(max_length=10, nullable=False)

    user: "User" = Relationship(back_populates="memberships")
    team: "Team" = Relationship(back_populates="memberships")
