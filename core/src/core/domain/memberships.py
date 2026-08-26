"""Team membership ownership rules (pure, no I/O; brief §5.2/§5.3, ticket 08)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from core.domain.authz import Role
from core.domain.errors import RuleViolationError

MSG_LAST_OWNER = "A Team must keep at least one owner"


@dataclass(frozen=True)
class MembershipRef:
    """A Team Membership as plain data (no SQLModel, no session)."""

    user_id: uuid.UUID
    role: Role


def assert_not_last_owner(members: Sequence[MembershipRef], target_user_id: uuid.UUID) -> None:
    """Raise when the change would leave the Team without an owner.

    Applied before demoting an owner (``owner`` → ``member``) and before
    removing an owner — including the owner demoting/removing themselves.
    ``members`` is the Team's full membership list; the target must be in
    it (the service loads the Membership first).

    Args:
        members: The Team's Memberships (user id + role).
        target_user_id: The User being demoted or removed.

    Raises:
        RuleViolationError: When the target is the Team's last owner.

    """
    target = next((m for m in members if m.user_id == target_user_id), None)
    if target is None or target.role is not Role.OWNER:
        return
    other_owners = [m for m in members if m.user_id != target_user_id and m.role is Role.OWNER]
    if not other_owners:
        raise RuleViolationError(MSG_LAST_OWNER)
