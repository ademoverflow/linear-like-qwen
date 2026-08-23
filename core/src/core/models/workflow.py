import uuid
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from core.models.team import Team
    from core.models.workflow_state import WorkflowState


class Workflow(SQLModel, table=True):
    """Model Class Workflow.

    Exactly one Workflow per Team (ADR 0005); it is the aggregate the
    Workflow States hang off.
    """

    __tablename__: ClassVar[str] = "workflows"

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
    team_id: uuid.UUID = Field(foreign_key="teams.id", unique=True, nullable=False)

    team: "Team" = Relationship(back_populates="workflow")
    states: list["WorkflowState"] = Relationship(back_populates="workflow")
