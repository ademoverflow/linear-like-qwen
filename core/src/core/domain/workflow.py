"""Workflow State rules (pure, no I/O; ADR 0005).

The domain layer works on plain ``WorkflowStateRule`` records; services convert
ORM rows into these before calling into this module.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from core.domain.errors import RuleViolationError, ValidationError

Category = Literal["backlog", "unstarted", "started", "completed", "canceled"]

CATEGORIES: tuple[Category, ...] = ("backlog", "unstarted", "started", "completed", "canceled")

# Categories that a Workflow must always keep at least one State of (brief §4.3).
REQUIRED_CATEGORIES: tuple[Category, ...] = ("unstarted", "started", "completed", "canceled")

MSG_CATEGORY_INVALID = "Category must be one of backlog, unstarted, started, completed or canceled"


@dataclass(frozen=True)
class WorkflowStateRule:
    """A Workflow State as plain data (no ids; ids stay in the service layer)."""

    name: str
    category: Category
    color: str
    position: int


# Default Workflow seeded for every new Team (brief §4.1). Colours follow the
# approved Phase 1 prototype (variant B).
DEFAULT_WORKFLOW_STATES: tuple[WorkflowStateRule, ...] = (
    WorkflowStateRule("Backlog", "backlog", "#a2a2a2", 0),
    WorkflowStateRule("Todo", "unstarted", "#737373", 1),
    WorkflowStateRule("In Progress", "started", "#f2c94c", 2),
    WorkflowStateRule("In Review", "started", "#fbc64d", 3),
    WorkflowStateRule("Done", "completed", "#4cb371", 4),
    WorkflowStateRule("Canceled", "canceled", "#d98c8c", 5),
)


def select_default_state(states: Sequence[WorkflowStateRule]) -> WorkflowStateRule:
    """Pick the default State for new Issues (brief §4.1).

    First State in category ``backlog``, else first in ``unstarted``; ties break
    on the smallest ``position``.

    Args:
        states: The States of one Workflow.

    Returns:
        The State new Issues start in.

    Raises:
        RuleViolationError: If the Workflow has neither a backlog nor an
            unstarted State.

    """
    for category in ("backlog", "unstarted"):
        candidates = [s for s in states if s.category == category]
        if candidates:
            return min(candidates, key=lambda s: s.position)
    msg = "Workflow has no backlog or unstarted state"
    raise RuleViolationError(msg)


@dataclass(frozen=True)
class TransitionEffect:
    """The timestamp effects of moving an Issue to a State (brief §4.2)."""

    completed_at: datetime | None
    canceled_at: datetime | None


def transition(target: WorkflowStateRule, now: datetime) -> TransitionEffect:
    """Compute the timestamp effects of a State transition (brief §4.2).

    Any State may move to any other State. The effect depends only on the
    target's category: entering ``completed`` sets ``completed_at`` (and
    clears ``canceled_at``); entering ``canceled`` sets ``canceled_at``
    (and clears ``completed_at``); any other target clears both.

    Args:
        target: The State the Issue moves to.
        now: The transition time (aware UTC), stamped by the service.

    Returns:
        The ``completed_at``/``canceled_at`` values to store.

    """
    if target.category == "completed":
        return TransitionEffect(completed_at=now, canceled_at=None)
    if target.category == "canceled":
        return TransitionEffect(completed_at=None, canceled_at=now)
    return TransitionEffect(completed_at=None, canceled_at=None)


STATE_NAME_MIN_LENGTH = 1
STATE_NAME_MAX_LENGTH = 50
STATE_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")

MSG_STATE_NAME_INVALID = "State name must be 1-50 characters"
MSG_STATE_COLOR_INVALID = "State colour must be a 6-digit hex value (e.g. #f2c94c)"
MSG_MIGRATION_TARGET_CATEGORY = "The migration target must be in the same category"


def validate_state_name(name: str) -> str:
    """Trim and validate a Workflow State name (1-50 chars).

    Args:
        name: The raw name as sent by the client.

    Returns:
        The trimmed name.

    Raises:
        ValidationError: If the trimmed name is shorter than 1 or longer
            than 50 characters.

    """
    stripped = name.strip()
    if not STATE_NAME_MIN_LENGTH <= len(stripped) <= STATE_NAME_MAX_LENGTH:
        raise ValidationError(MSG_STATE_NAME_INVALID)
    return stripped


def validate_state_color(color: str) -> str:
    """Validate a Workflow State colour (6-digit hex, ``#RRGGBB``).

    Args:
        color: The raw colour as sent by the client.

    Returns:
        The colour unchanged.

    Raises:
        ValidationError: If the colour is not a 6-digit hex value.

    """
    if not STATE_COLOR_PATTERN.match(color):
        raise ValidationError(MSG_STATE_COLOR_INVALID)
    return color


def validate_category(category: str) -> Category:
    """Validate a Workflow State category against the five known values.

    Args:
        category: The raw category as sent by the client.

    Returns:
        The category (a valid ``Category``).

    Raises:
        ValidationError: If the category is not one of the five.

    """
    if category not in CATEGORIES:
        raise ValidationError(MSG_CATEGORY_INVALID)
    return cast("Category", category)


def _categories_without(
    states: Sequence[WorkflowStateRule], excluded: WorkflowStateRule | None
) -> dict[str, int]:
    """Count the states per category, ignoring ``excluded``."""
    counts: dict[str, int] = {}
    for state in states:
        if (
            excluded is not None
            and state.name == excluded.name
            and state.position == excluded.position
        ):
            continue
        counts[state.category] = counts.get(state.category, 0) + 1
    return counts


def validate_state_deletion(
    states: Sequence[WorkflowStateRule], deleted: WorkflowStateRule
) -> None:
    """Enforce the category minimum after deleting ``deleted`` (brief §4.3).

    A Workflow must always keep at least one State in each of the required
    categories (``unstarted``, ``started``, ``completed``, ``canceled``);
    ``backlog`` is not in the minimum.

    Args:
        states: The Workflow's States, including the one being deleted.
        deleted: The State being deleted.

    Raises:
        RuleViolationError: If a required category would be left without a
            State (naming the first one, in required order).

    """
    counts = _categories_without(states, deleted)
    for category in REQUIRED_CATEGORIES:
        if counts.get(category, 0) == 0:
            msg = f"Workflow must keep at least one {category} state"
            raise RuleViolationError(msg)


def validate_category_change(
    states: Sequence[WorkflowStateRule],
    state: WorkflowStateRule,
    new_category: Category,
) -> None:
    """Enforce the category minimum when ``state`` changes category (brief §4.3).

    Args:
        states: The Workflow's States, including ``state`` (with its current
            category).
        state: The State being re-categorised.
        new_category: The category the State moves to.

    Raises:
        RuleViolationError: If the State's current category is required and
            this State is its only one (it would be left empty).

    """
    if new_category == state.category:
        return
    if state.category in REQUIRED_CATEGORIES:
        same_category = [
            s for s in states if s.category == state.category and s.position != state.position
        ]
        if not same_category:
            msg = f"Workflow must keep at least one {state.category} state"
            raise RuleViolationError(msg)


def assert_migration_target_same_category(
    source: WorkflowStateRule, target: WorkflowStateRule
) -> None:
    """Reject a delete-with-migrate target of a different category (brief §4.3).

    Wrong-category targets are invalid input (400), not an invariant
    violation (422 is reserved for the category minimum).

    Args:
        source: The State being deleted.
        target: The State its Issues move to.

    Raises:
        ValidationError: If the categories differ.

    """
    if target.category != source.category:
        raise ValidationError(MSG_MIGRATION_TARGET_CATEGORY)
