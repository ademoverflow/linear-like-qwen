import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import UUID, Column, DateTime, Integer, text
from sqlmodel import Field, Index, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.workflow import Workflow


class WorkflowState(SQLModel, table=True):
    """Model Class Workflow State (brief §2)."""

    __tablename__: ClassVar[str] = "workflow_states"
    __table_args__ = (
        Index("uq_workflow_states_workflow_name", "workflow_id", "name", unique=True),
        Index("uq_workflow_states_workflow_position", "workflow_id", "position", unique=True),
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
    workflow_id: uuid.UUID = Field(foreign_key="workflows.id", nullable=False)
    name: str = Field(max_length=50, nullable=False)
    category: str = Field(max_length=16, nullable=False)
    color: str = Field(max_length=7, nullable=False)
    position: int = Field(nullable=False)
    # Bumped on every State edit; clients must echo it (ADR 0008).
    version: int = Field(
        default=1,
        sa_column=Column(Integer, server_default=text("1"), nullable=False),
    )

    workflow: "Workflow" = Relationship(back_populates="states")
