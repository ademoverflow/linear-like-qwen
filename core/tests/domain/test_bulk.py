"""Tests for bulk action parsing (exactly one action). No database required."""

import uuid

import pytest
from core.domain.errors import ValidationError
from core.domain.issues import BulkAction, parse_bulk_action

STATE_ID = uuid.uuid4()
ASSIGNEE_ID = uuid.uuid4()
LABEL_A = uuid.uuid4()
LABEL_B = uuid.uuid4()


def test_parse_bulk_action_each_action_alone() -> None:
    """Each of the five actions is accepted on its own."""
    assert parse_bulk_action(
        state_id=STATE_ID,
        assignee_id=None,
        add_label_ids=(),
        remove_label_ids=(),
        archive=False,
    ) == BulkAction(state_id=STATE_ID)
    assert parse_bulk_action(
        state_id=None,
        assignee_id=ASSIGNEE_ID,
        add_label_ids=(),
        remove_label_ids=(),
        archive=False,
    ) == BulkAction(assignee_id=ASSIGNEE_ID)
    assert parse_bulk_action(
        state_id=None,
        assignee_id=None,
        add_label_ids=(LABEL_A,),
        remove_label_ids=(),
        archive=False,
    ) == BulkAction(add_label_ids=(LABEL_A,))
    assert parse_bulk_action(
        state_id=None,
        assignee_id=None,
        add_label_ids=(),
        remove_label_ids=(LABEL_A, LABEL_B),
        archive=False,
    ) == BulkAction(remove_label_ids=(LABEL_A, LABEL_B))
    assert parse_bulk_action(
        state_id=None, assignee_id=None, add_label_ids=(), remove_label_ids=(), archive=True
    ) == BulkAction(archive=True)


def test_parse_bulk_action_rejects_no_action() -> None:
    """A bulk request without any action is rejected (400)."""
    with pytest.raises(ValidationError, match="exactly one action"):
        parse_bulk_action(
            state_id=None, assignee_id=None, add_label_ids=(), remove_label_ids=(), archive=False
        )


def test_parse_bulk_action_rejects_multiple_actions() -> None:
    """Two or more actions at once are rejected (400)."""
    for state_id, assignee_id, add, remove, archive in (
        (STATE_ID, ASSIGNEE_ID, (), (), False),
        (STATE_ID, None, (LABEL_A,), (), False),
        (None, None, (LABEL_A,), (LABEL_B,), False),
        (STATE_ID, None, (), (), True),
        (None, ASSIGNEE_ID, (), (), True),
    ):
        with pytest.raises(ValidationError, match="only one action"):
            parse_bulk_action(
                state_id=state_id,
                assignee_id=assignee_id,
                add_label_ids=add,
                remove_label_ids=remove,
                archive=archive,
            )
