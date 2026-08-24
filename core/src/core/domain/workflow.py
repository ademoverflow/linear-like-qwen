"""Workflow State rules (pure, no I/O; ADR 0005).

The domain layer works on plain ``WorkflowStateRule`` records; services convert
ORM rows into these before calling into this module.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from core.domain.errors import RuleViolationError

Category = Literal["backlog", "unstarted", "started", "completed", "canceled"]

CATEGORIES: tuple[Category, ...] = ("backlog", "unstarted", "started", "completed", "canceled")

# Categories that a Workflow must always keep at least one State of (brief §4.3).
REQUIRED_CATEGORIES: tuple[Category, ...] = ("unstarted", "started", "completed", "canceled")


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
