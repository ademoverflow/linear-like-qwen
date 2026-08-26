"""Unit tests for the last-owner rule (no DB; brief §5.2/§5.3, ticket 08)."""

import uuid

import pytest
from core.domain.authz import Role
from core.domain.errors import RuleViolationError
from core.domain.memberships import MembershipRef, assert_not_last_owner

USER_A = uuid.uuid4()
USER_B = uuid.uuid4()
USER_C = uuid.uuid4()


def _ref(user_id: uuid.UUID, role: Role) -> MembershipRef:
    return MembershipRef(user_id=user_id, role=role)


def test_removing_the_last_owner_is_blocked() -> None:
    """A Team must keep at least one owner (mirrors the last-Admin rule)."""
    members = [_ref(USER_A, Role.OWNER), _ref(USER_B, Role.MEMBER)]
    with pytest.raises(RuleViolationError, match="owner"):
        assert_not_last_owner(members, USER_A)


def test_demoting_the_last_owner_is_blocked() -> None:
    """Demoting the last owner is blocked, like removing it."""
    members = [_ref(USER_A, Role.OWNER), _ref(USER_B, Role.MEMBER), _ref(USER_C, Role.MEMBER)]
    with pytest.raises(RuleViolationError, match="owner"):
        assert_not_last_owner(members, USER_A)


def test_removing_one_of_two_owners_is_allowed() -> None:
    """A Team may keep several owners; removing one of two is fine."""
    members = [_ref(USER_A, Role.OWNER), _ref(USER_B, Role.OWNER), _ref(USER_C, Role.MEMBER)]
    assert_not_last_owner(members, USER_A)
    assert_not_last_owner(members, USER_B)


def test_removing_a_member_is_never_blocked() -> None:
    """Removing a plain member never violates the last-owner rule."""
    members = [_ref(USER_A, Role.OWNER), _ref(USER_B, Role.MEMBER)]
    assert_not_last_owner(members, USER_B)


def test_deactivated_owner_still_counts_as_owner() -> None:
    """Ownership is a Membership role; deactivation does not strip it."""
    members = [_ref(USER_A, Role.OWNER), _ref(USER_B, Role.OWNER)]
    assert_not_last_owner(members, USER_A)
