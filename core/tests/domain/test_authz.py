"""Tests for the authorization matrix. No database required."""

import uuid

from core.domain.authz import (
    Action,
    Actor,
    IssueResource,
    Role,
    TeamResource,
    can,
)

TEAM_A = uuid.uuid4()
TEAM_B = uuid.uuid4()


def _actor(*, is_admin: bool = False, roles: dict[uuid.UUID, Role] | None = None) -> Actor:
    return Actor(user_id=uuid.uuid4(), is_admin=is_admin, team_roles=roles or {})


def test_admin_can_do_everything() -> None:
    """Workspace Admins pass every check (brief §5.2)."""
    admin = _actor(is_admin=True)
    for action in Action:
        assert can(admin, action, None)
    assert can(admin, Action.TEAM_VIEW, TeamResource(TEAM_A))
    assert can(admin, Action.ISSUE_VIEW, IssueResource(TEAM_B))


def test_non_admin_cannot_create_teams() -> None:
    """Team creation is an Admin-only action."""
    assert can(_actor(roles={TEAM_A: Role.OWNER}), Action.TEAM_CREATE, None) is False
    assert can(_actor(roles={TEAM_A: Role.MEMBER}), Action.TEAM_CREATE, None) is False


def test_team_actions_require_membership() -> None:
    """Members/owners of a Team may view it and its Issues; others may not."""
    owner = _actor(roles={TEAM_A: Role.OWNER})
    member = _actor(roles={TEAM_A: Role.MEMBER})
    outsider = _actor(roles={TEAM_B: Role.OWNER})

    for actor in (owner, member):
        assert can(actor, Action.TEAM_VIEW, TeamResource(TEAM_A))
        assert can(actor, Action.ISSUE_CREATE, IssueResource(TEAM_A))
        assert can(actor, Action.ISSUE_VIEW, IssueResource(TEAM_A))

    assert can(outsider, Action.TEAM_VIEW, TeamResource(TEAM_A)) is False
    assert can(outsider, Action.ISSUE_CREATE, IssueResource(TEAM_A)) is False
    assert can(outsider, Action.ISSUE_VIEW, IssueResource(TEAM_A)) is False


def test_actions_without_resource_are_denied_for_non_admins() -> None:
    """Team-scoped checks need a resource; without one, non-Admins are denied."""
    assert can(_actor(roles={TEAM_A: Role.OWNER}), Action.TEAM_VIEW, None) is False


def test_owner_only_actions_require_owner_role() -> None:
    """Label management and Issue archiving need the owner role (brief §5.2).

    Members are denied, owners and Admins pass; outsiders are denied.
    """
    owner = _actor(roles={TEAM_A: Role.OWNER})
    member = _actor(roles={TEAM_A: Role.MEMBER})
    outsider = _actor(roles={TEAM_B: Role.OWNER})

    for action in (
        Action.LABEL_CREATE,
        Action.LABEL_EDIT,
        Action.LABEL_DELETE,
        Action.ISSUE_ARCHIVE,
    ):
        assert can(owner, action, TeamResource(TEAM_A))
        assert can(_actor(is_admin=True), action, TeamResource(TEAM_A))
        assert can(member, action, TeamResource(TEAM_A)) is False
        assert can(outsider, action, TeamResource(TEAM_A)) is False


def test_label_view_is_member_scoped() -> None:
    """Listing a Team's Labels only needs a Membership."""
    member = _actor(roles={TEAM_A: Role.MEMBER})
    assert can(member, Action.LABEL_VIEW, TeamResource(TEAM_A))
    assert can(_actor(roles={TEAM_B: Role.OWNER}), Action.LABEL_VIEW, TeamResource(TEAM_A)) is False
