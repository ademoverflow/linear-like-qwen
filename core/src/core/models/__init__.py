"""SQLModel tables.

Every table module must be imported here: ``alembic/env.py`` does ``import core.models`` and
relies on this file to populate ``SQLModel.metadata`` for autogenerate.
"""

from core.models.activity import Activity
from core.models.comment import Comment
from core.models.invitation import Invitation
from core.models.issue import Issue
from core.models.issue_label import IssueLabel
from core.models.label import Label
from core.models.membership import Membership
from core.models.team import Team
from core.models.user import User
from core.models.workflow import Workflow
from core.models.workflow_state import WorkflowState
from core.models.workspace import Workspace

__all__ = [
    "Activity",
    "Comment",
    "Invitation",
    "Issue",
    "IssueLabel",
    "Label",
    "Membership",
    "Team",
    "User",
    "Workflow",
    "WorkflowState",
    "Workspace",
]
