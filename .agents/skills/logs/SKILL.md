---
name: logs
description: View Docker service logs for debugging. Use when investigating errors or checking service status.
argument-hint: "[core|webapp|db]"
---

View logs for Docker services.

Parse `$ARGUMENTS`:

| Argument | Service |
|----------|---------|
| `core` | Core API (FastAPI/uvicorn) |
| `webapp` | Webapp (React/Vite dev server) |
| `db` | Database (PostgreSQL) |
| (none) | All services |

## Command

Run: `docker compose logs --tail=100 <service>` (or omit service for all).

**NEVER use `-f` (follow) flag** — it will hang indefinitely.

## Process

1. Run the logs command with `--tail=100`.
2. Parse the output and highlight:
   - Errors and exceptions (tracebacks, ERROR level)
   - Warnings
   - Failed requests (4xx, 5xx status codes)
3. If debugging a specific issue, increase to `--tail=200` for more context.
4. Summarize findings for the user.
