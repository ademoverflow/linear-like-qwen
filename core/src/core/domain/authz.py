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


def can(actor: Actor, action: Action, resource: Resource) -> bool:
    """Decide whether ``actor`` may perform ``action`` on ``resource``.

    Workspace Admins may do everything in v1 (brief §5.2). Team-scoped actions
    require a Membership on the Team the resource belongs to; ``TEAM_CREATE``
    is Admin-only.

    Args:
        actor: The principal acting.
        action: The action to check.
        resource: The resource (or ``None`` for workspace-level actions).

    Returns:
        True if the action is allowed.

    """
    if actor.is_admin:
        return True
    if action is Action.TEAM_CREATE:
        return False
    if resource is None:
        return False
    return actor.team_roles.get(resource.team_id) is not None
