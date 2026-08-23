import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from pydantic import EmailStr
from sqlalchemy import UUID, Column, DateTime, Text, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.membership import Membership


class User(SQLModel, table=True):
    """Model Class User."""

    __tablename__: ClassVar[str] = "users"

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
    email: EmailStr = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_active: bool = Field(
        default=True, nullable=False, sa_column_kwargs={"server_default": text("true")}
    )
    display_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(
        default=None, max_length=500, sa_column=Column(Text, nullable=True)
    )
    is_admin: bool = Field(
        default=False, nullable=False, sa_column_kwargs={"server_default": text("false")}
    )

    memberships: list["Membership"] = Relationship(back_populates="user")
