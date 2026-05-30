import uuid
from datetime import datetime
from typing import ClassVar

from pydantic import EmailStr
from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, SQLModel


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
