# 0004 — Layering: pure `domain/`, transactional `services/`, thin `routers/`

**Status**: accepted

## Decision

- `core/src/core/domain/`: plain Python. **No imports from `sqlmodel`, `sqlalchemy`, `fastapi`
  or `core.database`.** Workflow transition rules, authorization (`can()`), identifier helpers,
  input invariants, `DomainError`s. Unit-tested in `core/tests/domain/` with no database.
- `core/src/core/services/`: one module per use-case family (`issues.py`, `teams.py`, `auth.py`,
  …). Owns the transaction (`async with session.begin()`), calls domain functions, writes
  `Activity` rows. This is the only layer that writes Activity.
- `core/src/core/routers/`: parse request → resolve auth dependency → call one service → return
  a response schema. No business logic.
- Frontend never re-implements a rule; it reads what the API exposes (e.g. allowed actions,
  the user's memberships/roles from `/auth/me`).

## Why

This is the test seam the brief and the `tdd` skill rely on: most rules get fast, DB-free tests;
HTTP tests cover wiring and authorization failures.
