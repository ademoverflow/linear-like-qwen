"""Tests for the workflow default-state rules. No database required."""

import pytest
from core.domain.errors import RuleViolationError
from core.domain.workflow import (
    DEFAULT_WORKFLOW_STATES,
    WorkflowStateRule,
    select_default_state,
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
