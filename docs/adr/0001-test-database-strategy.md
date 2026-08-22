# 0001 — Test database: dedicated `<db>_test`, migrated by the app lifespan, truncated per test

**Status**: accepted (bootstrap decision; revisit if the suite gets slow)

## Context

`core/tests` use `fastapi.testclient.TestClient`, whose lifespan runs `alembic upgrade head`
against `DATABASE_URL`. Without a dedicated database, tests would run against the dev data.
The app uses an asyncpg engine; `TestClient` runs the app on its own thread and event loop.

## Decision

- `core/tests/conftest.py` rewrites `DATABASE_URL` to `<original>_test` **before any `core`
  import** (settings are cached at import time), and creates that database on first use.
- The session-scoped `client` fixture enters the lifespan once, so the schema is migrated once
  per run with the real migrations. No `create_all`.
- An autouse fixture truncates every table in `SQLModel.metadata` after each test
  (`RESTART IDENTITY CASCADE`), keeping `alembic_version`.
- Test-side DB access is **synchronous psycopg2** (`pg` fixture, `make_user` factory). Tests do
  not touch `core.database.engine`: sharing an asyncpg pool between pytest's loop and the
  `TestClient` loop fails with "attached to a different loop".
- Tests under `core/tests/domain/` never touch the database; the truncate fixture skips them.

## Consequences

- `make test-core` works in Docker unchanged (`DATABASE_URL` comes from `.env`).
- Tests are not parallel-safe (shared database). Acceptable for now.
- Arrange state through the API once endpoints exist; fall back to `pg`/`make_user` only for
  things the API cannot create (e.g. the first Admin before bootstrap register exists).
