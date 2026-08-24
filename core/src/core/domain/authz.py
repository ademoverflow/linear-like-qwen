"""Authorization rules (pure, no I/O; brief §5.2, ADR 0004).

``can()`` is the single authorization entry point: services build an
``Actor`` from the authenticated user (via the service layer, never in a
router) and ask ``can()`` before touching a resource. Routers map the
outcomes: non-members get 404 on Team/Issue resources, other denials get 403.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    """Team role (Membership)."""

    OWNER = "owner"
    MEMBER = "member"


class Action(StrEnum):
    """Actions an actor may be checked for (grows per ticket)."""

    TEAM_CREATE = "team.create"
    TEAM_VIEW = "team.view"
    ISSUE_CREATE = "issue.create"
    ISSUE_VIEW = "issue.view"
    INVITATION_CREATE = "invitation.create"
    INVITATION_LIST = "invitation.list"
    USER_LIST = "user.list"
    USER_DEACTIVATE = "user.deactivate"
    USER_REACTIVATE = "user.reactivate"
    USER_PROMOTE = "user.promote"
    USER_DEMOTE = "user.demote"
    LABEL_VIEW = "label.view"
    LABEL_CREATE = "label.create"
    LABEL_EDIT = "label.edit"
    LABEL_DELETE = "label.delete"
    ISSUE_ARCHIVE = "issue.archive"
    ISSUE_RESTORE = "issue.restore"
    ISSUE_DELETE = "issue.delete"


@dataclass(frozen=True)
class Actor:
    """An authenticated principal as plain data (no SQLModel, no session)."""

    user_id: uuid.UUID
    is_admin: bool
    team_roles: dict[uuid.UUID, Role] = field(default_factory=dict)


@dataclass(frozen=True)
class TeamResource:
    """A Team addressed by id."""

    team_id: uuid.UUID


@dataclass(frozen=True)
class IssueResource:
    """An Issue, addressed by the Team it belongs to."""

    team_id: uuid.UUID


Resource = TeamResource | IssueResource | None

# Workspace-level actions that only workspace Admins may perform
# (brief §5.2; non-Admins are denied regardless of their Team roles).
ADMIN_ONLY_ACTIONS: frozenset[Action] = frozenset({Action.TEAM_CREATE, Action.ISSUE_DELETE})

# Team actions that require the owner role (brief §5.2; workspace Admins
# bypass the check, as always).
OWNER_ONLY_ACTIONS: frozenset[Action] = frozenset(
    {
        Action.LABEL_CREATE,
        Action.LABEL_EDIT,
        Action.LABEL_DELETE,
        Action.ISSUE_ARCHIVE,
        Action.ISSUE_RESTORE,
    }
)


def can(actor: Actor, action: Action, resource: Resource) -> bool:
    """Decide whether ``actor`` may perform ``action`` on ``resource``.

    Workspace Admins may do everything in v1 (brief §5.2). Team-scoped actions
    require a Membership on the Team the resource belongs to; the
    admin-only actions (``ADMIN_ONLY_ACTIONS``) are denied to everyone else;
    the owner-only actions (``OWNER_ONLY_ACTIONS``) require the ``owner`` role.

    Args:
        actor: The principal acting.
        action: The action to check.
        resource: The resource (or ``None`` for workspace-level actions).

    Returns:
        True if the action is allowed.

    """
    if actor.is_admin:
        return True
    if action in ADMIN_ONLY_ACTIONS:
        return False
    if resource is None:
        return False
    role = actor.team_roles.get(resource.team_id)
    if role is None:
        return False
    if action in OWNER_ONLY_ACTIONS:
        return role is Role.OWNER
    return True
