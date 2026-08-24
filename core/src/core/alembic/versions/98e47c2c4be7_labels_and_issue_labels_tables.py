"""labels and issue_labels tables.

Revision ID: 98e47c2c4be7
Revises: c0de8a243260
Create Date: 2026-08-24 13:02:07.077359

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98e47c2c4be7"
down_revision: str | Sequence[str] | None = "c0de8a243260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the Team-scoped labels table and the Issue↔Label link table (ticket 05)."""
    op.create_table(
        "labels",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("color", sqlmodel.sql.sqltypes.AutoString(length=7), nullable=False),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # One label name per Team (case-sensitive).
    op.create_index("uq_labels_team_name", "labels", ["team_id", "name"], unique=True)
    op.create_index(op.f("ix_labels_team_id"), "labels", ["team_id"], unique=False)
    op.create_table(
        "issue_labels",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("issue_id", sa.Uuid(), nullable=False),
        sa.Column("label_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["issues.id"],
        ),
        sa.ForeignKeyConstraint(
            ["label_id"],
            ["labels.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Each Issue carries each Label at most once.
    op.create_index(
        "uq_issue_labels_issue_label", "issue_labels", ["issue_id", "label_id"], unique=True
    )
    op.create_index(op.f("ix_issue_labels_label_id"), "issue_labels", ["label_id"], unique=False)

    # Project convention: every table gets an updated_at trigger (see .agents/skills/migrate).
    op.execute(
        "CREATE TRIGGER updated_at_trigger BEFORE UPDATE ON labels "
        "FOR EACH ROW EXECUTE PROCEDURE before_update_updated_at();"
    )
    op.execute(
        "CREATE TRIGGER updated_at_trigger BEFORE UPDATE ON issue_labels "
        "FOR EACH ROW EXECUTE PROCEDURE before_update_updated_at();"
    )


def downgrade() -> None:
    """Drop the labels and issue_labels tables."""
    op.execute("DROP TRIGGER IF EXISTS updated_at_trigger ON issue_labels")
    op.execute("DROP TRIGGER IF EXISTS updated_at_trigger ON labels")
    op.drop_index(op.f("ix_issue_labels_label_id"), table_name="issue_labels")
    op.drop_index("uq_issue_labels_issue_label", table_name="issue_labels")
    op.drop_table("issue_labels")
    op.drop_index(op.f("ix_labels_team_id"), table_name="labels")
    op.drop_index("uq_labels_team_name", table_name="labels")
    op.drop_table("labels")
