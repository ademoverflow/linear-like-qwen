# 0008 — Optimistic concurrency: `updated_at` on Issues, `version` on Workflow States

**Status**: accepted

## Context

Brief §3.3 requires `PATCH /issues/{id}` to carry the `updated_at` the client last saw
and reply `409` when stale. In the Phase 1 grill the maintainer wanted a version
field "for state" and delegated the final placement ("take the best approach").

## Decision

- **Issue**: exactly as the brief — the `PATCH` body carries the last-seen
  `updated_at`; the service compares it (full `timestamptz` precision) against the
  row's current value and raises `ConflictError` (409) on mismatch. No version
  column on `issues`.
- **Workflow States**: `workflow_states.version` (integer, starts at 1, bumped on
  every state-row change). Every state-edit operation (§4.3: create, rename,
  recolor, reorder, delete-with-migrate) requires the caller to echo the
  last-seen version of each state it changes; stale version → 409.

## Why

A state *transition* is a single-field atomic operation where last-write-wins plus
the Activity log is acceptable, and the brief's `updated_at` guard already covers
Issue field races (Postgres `timestamptz` is microsecond-precision). Concurrent
edits of state *definitions* are where conflicts genuinely break invariants — a
delete-with-migrate racing a reorder or recolor.

## Consequences

- The Issue API surface is unchanged from the brief; frontend optimistic updates
  (state/assignee/priority/labels) send the last-seen `updated_at` with the
  mutation.
- After a 409 the UI refetches the resource and toasts the conflict.
- Bulk operations (§4.4) remain unversioned, as the brief specifies them.
