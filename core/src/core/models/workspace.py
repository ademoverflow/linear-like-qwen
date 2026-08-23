import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, SQLModel


class Workspace(SQLModel, table=True):
    """Model Class Workspace.

    v1 is single-workspace (brief §2): one row acts as the tenant root so
    future FKs (Invitations, ...) have a target.
    """

    __tablename__: ClassVar[str] = "workspace"

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
