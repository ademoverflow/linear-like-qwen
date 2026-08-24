import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import UUID, Column, DateTime, text
from sqlmodel import Field, Index, SQLModel


class IssueLabel(SQLModel, table=True):
    """Model Class IssueLabel (M2M link between Issue and Label, brief §3.1).

    Carries its own primary key and timestamps (project convention); the
    Issue ``labels`` relationship joins through this table with explicit
    primary/secondary joins.
    """

    __tablename__: ClassVar[str] = "issue_labels"
    __table_args__ = (Index("uq_issue_labels_issue_label", "issue_id", "label_id", unique=True),)

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
    label_id: uuid.UUID = Field(foreign_key="labels.id", nullable=False)
