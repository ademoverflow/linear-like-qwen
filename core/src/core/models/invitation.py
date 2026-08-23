import uuid
from datetime import datetime
from typing import ClassVar

from pydantic import EmailStr
from sqlalchemy import UUID, Column, DateTime, ForeignKey, Text, text
from sqlmodel import Field, SQLModel


class Invitation(SQLModel, table=True):
    """Model Class Invitation (ADR 0012: workspace-level registration token).

    ``token`` stores the SHA-256 hex digest of the random token; the raw
    value is shown to the Admin once at creation and is not kept. One active
    Invitation per email (partial unique index in the migration); accepting
    an Invitation sets ``accepted_at``.
    """

    __tablename__: ClassVar[str] = "invitations"

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
    email: EmailStr = Field(index=True, nullable=False)
    token: str = Field(sa_column=Column(Text, nullable=False))
    invited_by: uuid.UUID = Field(sa_column=Column(UUID, ForeignKey("users.id"), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    accepted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
