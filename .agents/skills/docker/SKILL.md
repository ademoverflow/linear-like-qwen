---
name: docker
description: Docker Compose management - up, down, rebuild, restart, status
argument-hint: "<up|down|build|rebuild|restart|ps>"
disable-model-invocation: true
---

Manage Docker Compose services for the project.

Parse `$ARGUMENTS` and run the corresponding command:

| Argument | Command | Description |
|----------|---------|-------------|
| `up` | `make up` | Start all services in detached mode |
| `down` | `make down` | Stop all services |
| `build` | `make build` | Build all Docker images |
| `rebuild` | `make rebuild` | Rebuild with no cache and restart |
| `restart` | `make restart` | Restart all services |
| `ps` | `make ps` | Show running containers and status |

If no argument is provided, run `make ps` to show current status.

## Post-action checks

- After `up` or `restart`: run `make ps` to verify all services are healthy.
- If a service fails to start: automatically run `docker compose logs --tail=50 <service>` to diagnose.

## Important Notes

- `rebuild` does `--no-cache` build then `up -d` — only use when `build` is insufficient.
- Services: db (PostgreSQL), core (FastAPI), webapp (React), adminer (DB GUI).
- Ports: core=8999, webapp=8998, adminer=8997.
