"""SQLModel tables.

Every table module must be imported here: ``alembic/env.py`` does ``import core.models`` and
relies on this file to populate ``SQLModel.metadata`` for autogenerate.
"""

from core.models.user import User

__all__ = ["User"]
