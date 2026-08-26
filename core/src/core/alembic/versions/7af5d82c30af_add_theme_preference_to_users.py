"""add theme preference to users.

Revision ID: 7af5d82c30af
Revises: cc365a924274
Create Date: 2026-08-26 16:28:32.226896

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7af5d82c30af"
down_revision: str | Sequence[str] | None = "cc365a924274"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Only the ``users.theme`` column: autogen also proposed dropping
    hand-created indexes (activity.seq, invitations, labels) that it does
    not track; those are deliberately left untouched.
    """
    op.add_column(
        "users", sa.Column("theme", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "theme")
