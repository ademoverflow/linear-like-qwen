import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import UUID, Column, DateTime, Text, text
from sqlmodel import Field, SQLModel


class Activity(SQLModel, table=True):
    """Model Class Activity.

    Append-only audit row on an Issue (brief §2): who changed what, from → to.
    Written by the service layer only.
    """

    __tablename__: ClassVar[str] = "activity"

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
    issue_id: uuid.UUID = Field(foreign_key="issues.id", nullable=False)
    actor_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    kind: str = Field(max_length=50, nullable=False)
    field: str | None = Field(default=None, max_length=100)
    from_value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    to_value: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
