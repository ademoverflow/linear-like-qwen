"""Tests for the workflow default-state rules. No database required."""

from datetime import UTC, datetime

import pytest
from core.domain.errors import RuleViolationError
from core.domain.workflow import (
    CATEGORIES,
    DEFAULT_WORKFLOW_STATES,
    WorkflowStateRule,
    select_default_state,
    transition,
)


def test_default_workflow_has_six_states_in_order() -> None:
    """The seeded Workflow matches brief §4.1 (name, category, position)."""
    assert [(s.name, s.category, s.position) for s in DEFAULT_WORKFLOW_STATES] == [
        ("Backlog", "backlog", 0),
        ("Todo", "unstarted", 1),
        ("In Progress", "started", 2),
        ("In Review", "started", 3),
        ("Done", "completed", 4),
        ("Canceled", "canceled", 5),
    ]
    for state in DEFAULT_WORKFLOW_STATES:
        assert state.color


def test_selects_first_backlog_state() -> None:
    """New Issues start in the first backlog State (by position)."""
    states = [
        WorkflowStateRule("Later Backlog", "backlog", "#111111", 3),
        WorkflowStateRule("Backlog", "backlog", "#222222", 0),
        WorkflowStateRule("Todo", "unstarted", "#333333", 1),
    ]
    assert select_default_state(states).name == "Backlog"


def test_falls_back_to_first_unstarted_when_no_backlog() -> None:
    """Without a backlog State, the first unstarted State is used."""
    states = [
        WorkflowStateRule("Doing", "started", "#111111", 0),
        WorkflowStateRule("Second", "unstarted", "#222222", 2),
        WorkflowStateRule("First", "unstarted", "#333333", 1),
    ]
    assert select_default_state(states).name == "First"


def test_rejects_workflow_without_backlog_or_unstarted() -> None:
    """A Workflow that cannot host new Issues raises a rule violation."""
    states = [
        WorkflowStateRule("Doing", "started", "#111111", 0),
        WorkflowStateRule("Done", "completed", "#222222", 1),
    ]
    with pytest.raises(RuleViolationError):
        select_default_state(states)


def test_transition_into_completed_stamps_and_clears_canceled() -> None:
    """Entering a completed State sets completed_at and clears canceled_at."""
    effect = transition(
        WorkflowStateRule("Done", "completed", "#222222", 4),
        datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC),
    )
    assert effect.completed_at == datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    assert effect.canceled_at is None


def test_transition_into_canceled_stamps_and_clears_completed() -> None:
    """Entering a canceled State sets canceled_at and clears completed_at."""
    effect = transition(
        WorkflowStateRule("Canceled", "canceled", "#222222", 5),
        datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC),
    )
    assert effect.canceled_at == datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    assert effect.completed_at is None


def test_transition_leaving_completed_clears_both() -> None:
    """Leaving a completed State into anything else clears both timestamps."""
    effect = transition(
        WorkflowStateRule("In Progress", "started", "#222222", 2),
        datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC),
    )
    assert effect.completed_at is None
    assert effect.canceled_at is None


def test_transition_leaving_canceled_clears_both() -> None:
    """Leaving a canceled State into anything else clears both timestamps."""
    effect = transition(
        WorkflowStateRule("Todo", "unstarted", "#222222", 1),
        datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC),
    )
    assert effect.completed_at is None
    assert effect.canceled_at is None


def test_transition_full_category_matrix_any_to_any() -> None:
    """Any State may move to any State; the effect depends only on the target."""
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=UTC)
    for target_category in CATEGORIES:
        effect = transition(
            WorkflowStateRule("To", target_category, "#222222", 1),
            now,
        )
        assert effect.completed_at == (now if target_category == "completed" else None)
        assert effect.canceled_at == (now if target_category == "canceled" else None)
