# 0006 — Board DnD: `@dnd-kit/core` + `@dnd-kit/sortable`

**Status**: accepted

## Context

The Kanban board (§7.2.4) and the workflow state reordering (§7.2.6) need drag and drop.
§7.4 additionally requires full keyboard reachability and ARIA roles on board
columns/cards. Brief §7 asks that a DnD dependency be proposed in Phase 1.

## Decision

Use `@dnd-kit/core` + `@dnd-kit/sortable` for both the board and the workflow editor.

## Considered Options

- Native HTML5 DnD: zero dependencies, but weak keyboard and touch support — fails §7.4.
- `pragmatic-drag-and-drop` (Atlassian): performant and small, but no built-in
  keyboard/ARIA model.
- `@dnd-kit`: the only candidate with a mature accessibility story (keyboard sensors,
  ARIA live announcements), maintained, React 19 compatible, no runtime framework.

## Consequences

- Two new `webapp` dependencies (maintainer sign-off given in Phase 1).
- Board drag between columns maps to the single transition code path (brief §3.3);
  a failed drop rolls back via the TanStack Query mutation, per §7.4.
