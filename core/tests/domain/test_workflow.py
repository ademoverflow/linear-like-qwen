"""Tests for the workflow default-state rules. No database required."""

from datetime import UTC, datetime

import pytest
from core.domain.errors import RuleViolationError, ValidationError
from core.domain.workflow import (
    CATEGORIES,
    DEFAULT_WORKFLOW_STATES,
    Category,
    WorkflowStateRule,
    assert_migration_target_same_category,
    select_default_state,
    transition,
    validate_category,
    validate_category_change,
    validate_state_color,
    validate_state_deletion,
    validate_state_name,
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


def _state(name: str, category: Category, position: int) -> WorkflowStateRule:
    return WorkflowStateRule(name, category, "#222222", position)


# ---------------------------------------------------------------------------
# Category minimum on delete (brief §4.3)
# ---------------------------------------------------------------------------


def test_deleting_the_only_started_state_is_blocked() -> None:
    """A Team must keep at least one started State (ticket line 4)."""
    states = [
        _state("Todo", "unstarted", 0),
        _state("Doing", "started", 1),
        _state("Done", "completed", 2),
        _state("Nope", "canceled", 3),
    ]
    with pytest.raises(RuleViolationError, match="started"):
        validate_state_deletion(states, states[1])


def test_deleting_one_of_two_started_states_is_allowed() -> None:
    """The minimum is per category; one of two is fine."""
    states = [
        _state("Todo", "unstarted", 0),
        _state("Doing", "started", 1),
        _state("Review", "started", 2),
        _state("Done", "completed", 3),
        _state("Nope", "canceled", 4),
    ]
    validate_state_deletion(states, states[1])
    validate_state_deletion(states, states[2])


def test_deleting_the_only_backlog_state_is_allowed() -> None:
    """Backlog is not in the minimum (brief §4.3)."""
    states = [
        _state("Backlog", "backlog", 0),
        _state("Todo", "unstarted", 1),
        _state("Doing", "started", 2),
        _state("Done", "completed", 3),
        _state("Nope", "canceled", 4),
    ]
    validate_state_deletion(states, states[0])


def test_deleting_a_state_reports_the_missing_required_category() -> None:
    """The error names the first required category left without a State."""
    states = [_state("Doing", "started", 0), _state("Done", "completed", 1)]
    with pytest.raises(RuleViolationError, match="unstarted"):
        validate_state_deletion(states, states[1])


def test_default_workflow_allows_deleting_backlog_and_a_started_state() -> None:
    """Backlog is not required, and the default has two started States."""
    backlog = next(s for s in DEFAULT_WORKFLOW_STATES if s.category == "backlog")
    started = [s for s in DEFAULT_WORKFLOW_STATES if s.category == "started"]
    validate_state_deletion(list(DEFAULT_WORKFLOW_STATES), backlog)
    validate_state_deletion(list(DEFAULT_WORKFLOW_STATES), started[0])


def test_default_workflow_blocks_deleting_the_only_unstarted_state() -> None:
    """The seeded default has exactly one unstarted State (Todo)."""
    todo = next(s for s in DEFAULT_WORKFLOW_STATES if s.category == "unstarted")
    with pytest.raises(RuleViolationError, match="unstarted"):
        validate_state_deletion(list(DEFAULT_WORKFLOW_STATES), todo)


# ---------------------------------------------------------------------------
# Category minimum on category change (brief §4.3)
# ---------------------------------------------------------------------------


def test_changing_the_only_canceled_state_away_is_blocked() -> None:
    """Re-categorising the last canceled State would empty the category."""
    states = [
        _state("Todo", "unstarted", 0),
        _state("Doing", "started", 1),
        _state("Done", "completed", 2),
        _state("Nope", "canceled", 3),
    ]
    with pytest.raises(RuleViolationError, match="canceled"):
        validate_category_change(states, states[3], "started")


def test_changing_one_of_two_canceled_states_away_is_allowed() -> None:
    """The minimum is one State per category; a second canceled State may move."""
    states = [
        _state("Todo", "unstarted", 0),
        _state("Doing", "started", 1),
        _state("Done", "completed", 2),
        _state("Nope", "canceled", 3),
        _state("Also Nope", "canceled", 4),
    ]
    validate_category_change(states, states[3], "backlog")


def test_changing_a_backlog_state_category_is_allowed() -> None:
    """Backlog is not required, so its States may be re-categorised freely."""
    states = [
        _state("Backlog", "backlog", 0),
        _state("Todo", "unstarted", 1),
        _state("Doing", "started", 2),
        _state("Done", "completed", 3),
        _state("Nope", "canceled", 4),
    ]
    validate_category_change(states, states[0], "unstarted")


# ---------------------------------------------------------------------------
# Delete-with-migrate target (brief §4.3)
# ---------------------------------------------------------------------------


def test_migration_target_must_match_the_source_category() -> None:
    """A wrong-category target is invalid input (400), not an invariant (422)."""
    source = _state("Doing", "started", 1)
    assert_migration_target_same_category(source, _state("Review", "started", 3))
    with pytest.raises(ValidationError, match="same category"):
        assert_migration_target_same_category(source, _state("Done", "completed", 2))


# ---------------------------------------------------------------------------
# State name / colour input rules
# ---------------------------------------------------------------------------


def test_category_validation_accepts_only_the_five() -> None:
    """Only the five canonical category values are accepted."""
    for category in CATEGORIES:
        assert validate_category(category) == category
    for invalid in ("", "in-progress", "STARTED", "done "):
        with pytest.raises(ValidationError):
            validate_category(invalid)


def test_state_name_is_trimmed_and_bounded() -> None:
    """Names are trimmed and must be 1-50 characters."""
    assert validate_state_name("  In Progress  ") == "In Progress"
    assert len(validate_state_name("x" * 50)) == 50
    with pytest.raises(ValidationError):
        validate_state_name("   ")
    with pytest.raises(ValidationError):
        validate_state_name("x" * 51)


def test_state_color_must_be_hex() -> None:
    """Colours must be #RRGGBB hex strings."""
    assert validate_state_color("#f2c94c") == "#f2c94c"
    assert validate_state_color("#F2C94C") == "#F2C94C"
    for invalid in ("f2c94c", "#f2c94", "#f2c94cc", "f2c94z", ""):
        with pytest.raises(ValidationError):
            validate_state_color(invalid)
