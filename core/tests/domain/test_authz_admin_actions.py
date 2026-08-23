"""Admin-only workspace actions: invitations and user management (brief §5.3)."""

import uuid

from core.domain.authz import Action, Actor, can

ADMIN_ONLY_ACTIONS = (
    Action.INVITATION_CREATE,
    Action.INVITATION_LIST,
    Action.USER_LIST,
    Action.USER_DEACTIVATE,
    Action.USER_REACTIVATE,
    Action.USER_PROMOTE,
    Action.USER_DEMOTE,
)


def test_non_admins_are_denied_admin_workspace_actions() -> None:
    """Invitations and user management are workspace-Admin privileges only."""
    outsider = Actor(user_id=uuid.uuid4(), is_admin=False, team_roles={})
    for action in ADMIN_ONLY_ACTIONS:
        assert can(outsider, action, None) is False


def test_admins_are_allowed_admin_workspace_actions() -> None:
    """Workspace Admins pass every admin-only workspace action."""
    admin = Actor(user_id=uuid.uuid4(), is_admin=True, team_roles={})
    for action in ADMIN_ONLY_ACTIONS:
        assert can(admin, action, None)
