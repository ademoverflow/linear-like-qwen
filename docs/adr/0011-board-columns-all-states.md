# 0011 — Board: one column per Workflow State, including Backlog and Canceled

**Status**: accepted

## Context

Brief §7.2.4: the Board is a Kanban by Workflow State. Whether "active" categories
only (as in Linear) or all states were open. Maintainer chose all.

## Decision

The board renders one column per state of the Team's Workflow — including
`backlog` and `canceled` states. Column order follows `position`.

## Consequences

- No category special-casing in the board UI; reordering states reorders columns.
- Teams with many states get a wide board (horizontal scroll).
- Dragging a card between columns is a transition through the single domain
  code path; dropping into a `completed`/`canceled` state sets/clears the
  timestamps per brief §4.2.
