# Core API

FastAPI backend service for the application.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.115 |
| Runtime | Python 3.13 |
| ORM | SQLModel (SQLAlchemy wrapper) |
| Database | PostgreSQL 17 (async via asyncpg) |
| Migrations | Alembic |
| Auth | JWT (PyJWT) + Argon2id |
| Validation | Pydantic |
| Package Manager | uv |

## Project Structure

```
core/
├── src/core/
│   ├── __init__.py         # Package version
│   ├── __main__.py         # Entry point (starts Uvicorn)
│   ├── main.py             # FastAPI app initialization
│   ├── settings.py         # Pydantic Settings config
│   ├── database.py         # Async SQLAlchemy engine
│   │
│   ├── routers/            # API route handlers
│   │   ├── __init__.py
│   │   └── health.py       # GET /health
│   │
│   ├── models/             # SQLModel data models
│   │   ├── user.py         # User model
│   │   └── serializer.py   # JSON serialization (orjson)
│   │
│   ├── security/           # Authentication
│   │   ├── token.py        # JWT creation/validation
│   │   └── password.py     # Argon2id hashing
│   │
│   ├── middlewares/        # Request middleware
│   │   └── user.py         # User extraction from JWT
│   │
│   ├── logger/             # Logging utilities
│   │   ├── logger.py       # Custom logger setup
│   │   └── levels.py       # Log level enum
│   │
│   ├── misc/               # Utilities
│   │   └── uptime.py       # Process uptime
│   │
│   └── alembic/            # Database migrations
│       ├── alembic.ini
│       ├── env.py
│       └── versions/
│
├── tests/                  # Test suite
│   └── test_health.py
│
├── Dockerfile              # Multi-stage Docker build
├── pyproject.toml          # Dependencies
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (status, uptime, version) |
| GET | `/docs` | Swagger UI documentation |
| GET | `/redoc` | ReDoc documentation |

## Development

### Running Locally

```bash
# Install dependencies
uv sync

# Start server
uv run python -m core
```

Server runs on `http://0.0.0.0:80` by default (configured via `CORE_SERVER_HOST` and `CORE_SERVER_PORT`).

### With Docker

```bash
# From repository root
docker compose up core
```

Accessible at `http://localhost:8999`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CORE_SERVER_HOST` | Yes | Server bind address (e.g., `0.0.0.0`) |
| `CORE_SERVER_PORT` | Yes | Server port (e.g., `80`) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `CORE_JWT_SECRET_KEY` | Yes | JWT signing secret |
| `CORE_JWT_ALGORITHM` | Yes | JWT algorithm (e.g., `HS256`) |
| `CORE_JWT_EXPIRATION_TIMEDELTA_MINUTES` | Yes | Token expiration in minutes |
| `WEBAPP_URL` | Yes | Frontend URL for CORS |
| `COOKIE_DOMAIN` | Yes | Domain for auth cookies |
| `DEV_MODE` | No | Enable development mode (default: `false`) |

## Database

### Connection

Uses async SQLAlchemy with asyncpg driver. Connection configured via `DATABASE_URL`:

```
postgresql://user:password@host:5432/database
```

### Migrations

Migrations auto-run on application startup. Manual commands:

```bash
# Generate a new migration
alembic revision --autogenerate -m "Add users table"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Models

SQLModel combines SQLAlchemy ORM with Pydantic validation:

```python
from sqlmodel import Field, SQLModel

class User(SQLModel, table=True):
    id: uuid.UUID = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = True
```

## Authentication

### Password Hashing

Uses Argon2id with secure defaults:

```python
from core.security.password import hash_password, verify_password

hashed = hash_password("plaintext")
is_valid = verify_password("plaintext", hashed)
```

### JWT Tokens

```python
from core.security.token import create_access_token
from datetime import timedelta

token = create_access_token(
    data={"sub": str(user_id)},
    expires_delta=timedelta(minutes=60)
)
```

### Auth Middleware

Inject current user into route handlers:

```python
from typing import Annotated
from fastapi import Depends
from core.middlewares.user import get_current_user
from core.models.user import User

@router.get("/me")
async def get_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
```

Supports both:
- Cookie-based auth (for web app)
- Bearer token in `Authorization` header (for mobile/API clients)

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=core

# Run specific test
uv run pytest tests/test_health.py -v
```

Test pattern using FastAPI TestClient:

```python
from fastapi.testclient import TestClient
from core.main import app

client = TestClient(app)

def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

## Code Quality

```bash
# Format code
poe fix_format

# Check linting
poe check_lint

# Type check
poe type_check

# All checks
./scripts/code-quality-checkers.sh
```

## Docker

Multi-stage Dockerfile with `dev` and `prod` targets:

```bash
# Development (with hot reload)
docker build --target dev -t core:dev .

# Production (minimal image)
docker build --target prod -t core:prod .
```
