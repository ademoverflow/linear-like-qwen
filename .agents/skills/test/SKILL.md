---
name: test
description: Run tests for core (pytest) or webapp (vitest). Use when code changes need verification.
argument-hint: "[core|webapp|<test-file-path>]"
---

Run tests for the project.

## Scope

Parse `$ARGUMENTS` to determine what to test:

- No arguments → run all tests: `make test-core`, `make test-webapp`
- `core` → `make test-core` (pytest in Docker container)
- `webapp` → `make test-webapp` (vitest on host)
- A specific file path (e.g., `core/tests/test_health.py`) → run that file directly:
  - If it starts with `core/`: `docker compose exec core bash -c 'uv run pytest <path> -v'`
  - If it starts with `webapp/`: `pnpm --filter webapp run test <path>`
- A test function name with `-k` flag: pass through, e.g., `core -k test_health` → `docker compose exec core bash -c 'uv run pytest core/tests -v -k test_health'`

## Process

1. Run the appropriate test command(s).
2. Report the results clearly: number of tests passed, failed, skipped.
3. If tests fail:
   a. Read the failing test and the source code it tests.
   b. Determine if the failure is in the test or the source code.
   c. Suggest or apply fixes as appropriate.

## Important Notes

- Core tests run inside the Docker container (they need the database).
- Frontend tests run on the host via pnpm.
- Test fixtures are in `core/tests/conftest.py` if present.
