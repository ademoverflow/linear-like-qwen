"""Unit tests for the last-active-Admin rule (no DB; brief §5.3)."""

import pytest
from core.domain.errors import RuleViolationError
from core.domain.users import assert_last_admin_rule


def test_demoting_the_last_active_admin_is_blocked() -> None:
    """Demoting the last active Admin is a rule violation."""
    with pytest.raises(RuleViolationError, match="last active Admin"):
        assert_last_admin_rule(target_is_admin=True, target_is_active=True, other_active_admins=0)


def test_deactivating_the_last_active_admin_is_blocked() -> None:
    """Deactivating the last active Admin is a rule violation."""
    with pytest.raises(RuleViolationError, match="last active Admin"):
        assert_last_admin_rule(target_is_admin=True, target_is_active=True, other_active_admins=0)


def test_change_allowed_when_another_active_admin_exists() -> None:
    """Changes are allowed while another active Admin remains."""
    assert_last_admin_rule(target_is_admin=True, target_is_active=True, other_active_admins=1)


def test_deactivated_admin_can_be_demoted() -> None:
    """A deactivated Admin holds no active privilege, so never blocks."""
    assert_last_admin_rule(target_is_admin=True, target_is_active=False, other_active_admins=0)


def test_non_admin_targets_are_never_blocked() -> None:
    """Non-Admin targets never trigger the rule."""
    assert_last_admin_rule(target_is_admin=False, target_is_active=True, other_active_admins=0)
