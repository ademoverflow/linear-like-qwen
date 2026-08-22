# 0005 — Workflow: a dedicated `workflows` table, not states-on-team

**Status**: accepted

## Context

Brief §2: each Team owns exactly one Workflow, and a separate `workflows` table was left
open ("decide in Phase 1"). Maintainer decision: use the table.

## Decision

- `workflows` table: `id`, `team_id` (unique — exactly one Workflow per Team), timestamps.
  No name column; the Workflow is an aggregate, not a labeled entity.
- `workflow_states` reference `workflow_id` (not `team_id`), with `name`, `category`,
  `color`, `position`; unique `(workflow_id, name)` and `(workflow_id, position)`.
- Team creation seeds the Workflow and the six default states (§4.1) in one transaction.
- Domain rules take a Workflow scope: transitions and the "≥ 1 state per category"
  invariant are validated per Workflow (equivalent to per-Team at 1:1).

## Consequences

- A future multi-workflow feature is an insert, not a data migration.
- Issue creation needs the Team's Workflow to resolve the default state; the service
  loads it once and passes it to the domain layer.
