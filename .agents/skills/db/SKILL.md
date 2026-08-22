---
name: db
description: Database utilities - shell, history, current revision, upgrade, downgrade
argument-hint: "<shell|history|current|upgrade|downgrade>"
disable-model-invocation: true
---

Run database utility commands for the project.

Parse `$ARGUMENTS` and run the corresponding command:

| Argument | Command | Description |
|----------|---------|-------------|
| `shell` | `make db-shell` | Open psql shell |
| `history` | `make db-history` | Show migration history |
| `current` | `make db-current` | Show current migration revision |
| `upgrade` | `make db-upgrade` | Apply all pending migrations |
| `downgrade` | `make db-downgrade` | Revert the last migration |

If no argument is provided, run `make db-current` and `make db-history` to show current state.

## Important Notes

- All database commands run inside the Docker core container via `docker compose exec`.
- For `shell`: this is interactive and cannot run in Claude Code. Instead, tell the user to run `make db-shell` themselves. If they need a specific query, offer to run it via: `docker compose exec db psql -U admin -d db -c "<query>"`
- For `downgrade`: warn the user that this is destructive and confirm before running.
- The database is PostgreSQL 17, user `admin`, database `db`.
