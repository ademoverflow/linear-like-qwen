# CLAUDE.md - AI Assistant Guide

This document provides essential context for AI assistants working with this codebase.

## Project Overview

Full-stack monorepo with:
- **Backend**: Python 3.13+ / FastAPI
- **Frontend**: TypeScript / React 19 / Vite
- **Database**: PostgreSQL 17
- **Containerization**: Docker Compose

All development commands are available via `make`. Run `make help` to see all targets.

## Code Quality Standards

### Python (Ruff + MyPy)

Configuration in `/pyproject.toml`:
- Line length: 100 characters
- Indent: 4 spaces
- Quote style: double quotes
- All rules enabled with specific ignores (see `[tool.ruff.lint]`)

```bash
make check-format   # Check formatting
make fix-format     # Fix formatting
make check-lint     # Run linting
make check-sort     # Check import order
make fix-sort       # Fix import order
make type-check     # Run mypy
make check-python   # Run all Python checks
make fix            # Fix all auto-fixable Python issues
```

### TypeScript/JavaScript (Biome)

Configuration in `/biome.json`:
- Tab indentation
- Double quotes
- Organize imports enabled

```bash
make lint-webapp    # Run linter
make format-webapp  # Run formatter
make check-webapp   # Run both
```

### All Checks

```bash
make check          # Run ALL checks (Python + webapp)
```

### Commit Messages

Conventional commits enforced via commitlint. Format: `type(scope): description`

Allowed types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`, `wip`

## Project Structure

```
/
├── core/                    # Python FastAPI backend
│   ├── src/core/
│   │   ├── __main__.py     # Entry point
│   │   ├── main.py         # FastAPI app setup
│   │   ├── settings.py     # Pydantic settings
│   │   ├── database.py     # Async SQLAlchemy setup
│   │   ├── routers/        # API route handlers
│   │   ├── models/         # SQLModel data models
│   │   ├── security/       # JWT + password hashing
│   │   ├── middlewares/    # Auth middleware
│   │   ├── logger/         # Structured logging
│   │   └── alembic/        # Database migrations
│   └── tests/
├── webapp/                  # React SPA frontend
│   └── src/
│       ├── main.tsx        # App bootstrap with router
│       ├── env.ts          # T3 Env configuration
│       ├── pages/          # Page components
│       └── integrations/   # Library integrations
├── scripts/                 # Development utilities
├── .claude/skills/          # Claude Code slash commands
├── Makefile                 # Development command runner
├── compose.yaml            # Docker orchestration
└── bootstrap.sh            # Project initialization
```

## Design Patterns

### Backend (Python/FastAPI)

**Router Pattern**:
```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ResponseModel(BaseModel):
    field: str

@router.get("/endpoint", tags=["Tag"])
def handler() -> ResponseModel:
    return ResponseModel(field="value")
```

**SQLModel ORM**:
```python
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, UUID, text

class Model(SQLModel, table=True):
    id: uuid.UUID = Field(
        sa_column=Column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    )
```

**Async Database Session**:
```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session

async def handler(session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    ...
```

**Settings Management**:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Password Hashing** (Argon2id):
```python
from core.security.password import hash_password, verify_password
```

**JWT Tokens**:
```python
from core.security.token import create_access_token
from datetime import timedelta

token = create_access_token({"sub": user_id}, timedelta(minutes=60))
```

### Frontend (React/TypeScript)

**TanStack Router** (code-based):
```typescript
import { createRoute } from "@tanstack/react-router";

const route = createRoute({
    getParentRoute: () => rootRoute,
    path: "/path",
    component: Component,
});
```

**TanStack Query**:
```typescript
import { useQuery } from "@tanstack/react-query";

const { data } = useQuery({
    queryKey: ["key"],
    queryFn: () => fetch("/api/endpoint").then(r => r.json()),
});
```

**Environment Variables** (T3 Env + Zod):
```typescript
import { env } from "@/env";
// Only access validated env vars through this import
```

## Testing

```bash
make test-core      # Run Python tests (pytest, inside Docker)
make test-webapp    # Run JS tests (vitest, on host)
```

### Python Tests

Pattern: FastAPI TestClient with assertions
```python
from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

def test_endpoint() -> None:
    response = client.get("/endpoint")
    assert response.status_code == 200
```

### JavaScript Tests

Framework: Vitest + Testing Library

## Development Workflow

### Docker Services
```bash
make up             # Start all services
make down           # Stop all services
make build          # Build Docker images
make rebuild        # Rebuild and restart (no cache)
make restart        # Restart all services
make ps             # Show container status
make logs           # Tail all logs
make logs-core      # Tail core logs
make logs-webapp    # Tail webapp logs
make logs-db        # Tail database logs
```

### Ports
| Service | Port |
|---------|------|
| Adminer | 8997 |
| Webapp  | 8998 |
| Core API| 8999 |

### Database Migrations
Migrations auto-run on startup via FastAPI lifespan. Manual commands:
```bash
make db-migrate MSG="description"   # Create new migration
make db-upgrade                      # Apply all pending migrations
make db-downgrade                    # Revert last migration
make db-history                      # Show migration history
make db-current                      # Show current revision
make db-shell                        # Open psql shell
```

### Shell Access
```bash
make shell-core     # Bash into core container
make shell-webapp   # Shell into webapp container
make shell-db       # Bash into database container
```

### Utilities
```bash
make install        # Install all dependencies (Python + JS)
make clean          # Remove caches and build artifacts
make ip             # Show local IP and service URLs
make update-ip      # Update .env with current local IP
```

## Claude Code Skills

Available via `/skill-name` in Claude Code:

| Skill | Description |
|-------|-------------|
| `/check` | Run code quality checks and auto-fix |
| `/db` | Database utilities (shell, history, migrations) |
| `/docker` | Docker Compose management |
| `/fix-lint` | Auto-fix linting and formatting |
| `/logs` | View Docker service logs |
| `/migrate` | Create and apply Alembic migrations |
| `/new-component` | Scaffold a React component |
| `/new-endpoint` | Scaffold a FastAPI endpoint |
| `/new-route` | Scaffold a TanStack Router route |
| `/test` | Run tests |

## Key Files Reference

| Purpose | File |
|---------|------|
| Makefile | `Makefile` |
| FastAPI app | `core/src/core/main.py` |
| Settings | `core/src/core/settings.py` |
| Database | `core/src/core/database.py` |
| User model | `core/src/core/models/user.py` |
| Auth middleware | `core/src/core/middlewares/user.py` |
| React entry | `webapp/src/main.tsx` |
| Env validation | `webapp/src/env.ts` |
| Docker setup | `compose.yaml` |
| Python config | `pyproject.toml` |
| JS config | `biome.json` |
| Skills | `.claude/skills/` |
