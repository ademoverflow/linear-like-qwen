# 0010 — Issue numbers: `next_issue_number` column on `teams`

**Status**: accepted

## Context

Brief §3.2: the per-Team Issue counter must never be reused and must be allocated
inside the creating transaction; a `team_issue_counters` row or a column on
`teams` were both allowed. Maintainer chose the column.

## Decision

- `teams.next_issue_number` (integer, default 1).
- Issue creation locks the Team row (`SELECT … FOR UPDATE`) in the same transaction
  that inserts the Issue, allocates the number from the column and increments it.
- A concurrency test creates N Issues in parallel and asserts no duplicate numbers
  (brief §3.2).

## Consequences

- The Team row is briefly hot-locked per Issue creation — fine at v1 scale.
- No separate counter table to keep in sync; archiving/deleting an Issue never
  touches the counter.
