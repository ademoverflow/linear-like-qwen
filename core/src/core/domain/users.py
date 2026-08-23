"""Workspace Admin rules (pure, no I/O; brief §5.3)."""

from core.domain.errors import RuleViolationError

MSG_LAST_ADMIN = "The last active Admin cannot be demoted or deactivated"


def assert_last_admin_rule(
    *, target_is_admin: bool, target_is_active: bool, other_active_admins: int
) -> None:
    """Raise when the change would leave the Workspace without an active Admin.

    Applied before demoting an Admin and before deactivating an active
    Admin. A deactivated Admin holds no active privilege, so changing them
    never blocks; ``other_active_admins`` counts active Admins excluding the
    target.

    Args:
        target_is_admin: Whether the target User is an Admin.
        target_is_active: Whether the target User is active.
        other_active_admins: Active Admins besides the target.

    Raises:
        RuleViolationError: When the target is the last active Admin.

    """
    if target_is_admin and target_is_active and other_active_admins == 0:
        raise RuleViolationError(MSG_LAST_ADMIN)
