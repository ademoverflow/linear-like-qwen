"""add_comments_table.

Revision ID: cc365a924274
Revises: 98e47c2c4be7
Create Date: 2026-08-24 16:09:23.009232

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cc365a924274"
down_revision: str | Sequence[str] | None = "98e47c2c4be7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the comments table (ticket 06)."""
    op.create_table(
        "comments",
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
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        # Cascades so a hard-deleted Issue (ticket 07) removes its Comments
        # without extra code.
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_issue_id", "comments", ["issue_id"], unique=False)
    op.create_index("ix_comments_author_id", "comments", ["author_id"], unique=False)

    # Which Comment a comment.* Activity row is about (ticket 06). Nullable and
    # deliberately FK-less: a comment.deleted row outlives the Comment.
    op.add_column(
        "activity",
        sa.Column(
            "comment_id",
            sa.Uuid(),
            nullable=True,
        ),
    )
    op.create_index("ix_activity_comment_id", "activity", ["comment_id"], unique=False)

    # Project convention: every table gets an updated_at trigger (see .agents/skills/migrate).
    op.execute(
        "CREATE TRIGGER updated_at_trigger BEFORE UPDATE ON comments "
        "FOR EACH ROW EXECUTE PROCEDURE before_update_updated_at();"
    )


def downgrade() -> None:
    """Drop the comments table."""
    op.drop_index("ix_activity_comment_id", table_name="activity")
    op.drop_column("activity", "comment_id")
    op.execute("DROP TRIGGER IF EXISTS updated_at_trigger ON comments")
    op.drop_index("ix_comments_issue_id", table_name="comments")
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_table("comments")
