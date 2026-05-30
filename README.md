# Ademoverflow Template

## Description

A production-ready monorepo template for full-stack web applications with Python/FastAPI backend and React/TypeScript frontend.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Webapp (React SPA)                        │
│                    localhost:8998                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐    │
│  │  TanStack   │ │  TanStack   │ │    Tailwind CSS     │    │
│  │   Router    │ │    Query    │ │                     │    │
│  └─────────────┘ └─────────────┘ └─────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Core API (FastAPI)                         │
│                   localhost:8999                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐    │
│  │   SQLModel  │ │     JWT     │ │      Alembic        │    │
│  │     ORM     │ │    Auth     │ │    Migrations       │    │
│  └─────────────┘ └─────────────┘ └─────────────────────┘    │
└─────────────────────────┬───────────────────────────────────┘
                          │ TCP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   PostgreSQL 17                              │
│                   db:5432                                    │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite, TanStack Router/Query, Tailwind CSS |
| Backend | Python 3.13, FastAPI, SQLModel, Alembic, Pydantic |
| Database | PostgreSQL 17 |
| Auth | JWT (PyJWT) + Argon2id password hashing |
| Package Managers | pnpm (Node), uv (Python) |
| Code Quality | Biome (JS/TS), Ruff + MyPy (Python) |
| Containers | Docker, Docker Compose |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [pnpm](https://pnpm.io/installation) (v10.23.0+)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)

## Quick Start

### 1. Bootstrap the Project (Optional)

If you're using this as a template for a new project:

```bash
./bootstrap.sh
```

This will prompt you for:
- Project name
- Project description
- Base port number

### 2. Configure Environment

```bash
cp env.example .env
```

Edit `.env` with your local settings (especially `WEBAPP_URL` and `COOKIE_DOMAIN` with your local IP).

### 3. Start Development Stack

```bash
docker compose up
```

### 4. Access Services

| Service | URL | Description |
|---------|-----|-------------|
| Webapp | http://localhost:8998 | React frontend |
| Core API | http://localhost:8999 | FastAPI backend |
| API Docs | http://localhost:8999/docs | Swagger UI |
| Adminer | http://localhost:8997 | Database admin |

## Project Structure

```
/
├── core/                    # Python FastAPI backend
│   ├── src/core/           # Application source
│   ├── tests/              # Backend tests
│   ├── Dockerfile          # Multi-stage Docker build
│   ├── pyproject.toml      # Dependencies
│   └── README.md           # Backend documentation
│
├── webapp/                  # React TypeScript frontend
│   ├── src/                # Application source
│   ├── Dockerfile          # Multi-stage Docker build
│   ├── package.json        # Dependencies
│   └── README.md           # Frontend documentation
│
├── scripts/                 # Development utilities
│   ├── clean-cache.sh      # Clear build caches
│   ├── clean-node.sh       # Clean node_modules
│   ├── code-quality-checkers.sh
│   └── update-package-version.sh
│
├── .github/                 # CI/CD workflows
│   └── workflows/
│       ├── commitlint.yml  # Commit message validation
│       └── semantic-release.yml
│
├── compose.yaml            # Docker Compose config
├── pyproject.toml          # Root Python config + tools
├── package.json            # Root Node config
├── biome.json              # JS/TS linting config
├── bootstrap.sh            # Project initialization
├── CLAUDE.md               # AI assistant guide
└── env.example             # Environment template
```

## Development

### Running Locally (without Docker)

**Backend:**
```bash
cd core
uv sync
uv run python -m core
```

**Frontend:**
```bash
cd webapp
pnpm install
pnpm dev
```

### Code Quality

**Python:**
```bash
poe check_format    # Check formatting
poe check_lint      # Check linting
poe type_check      # Run mypy
```

**TypeScript:**
```bash
cd webapp
pnpm lint           # Run linter
pnpm check          # Run linter + formatter
```

### Testing

**Backend:**
```bash
uv run pytest core/tests/
```

**Frontend:**
```bash
cd webapp && pnpm test
```

### Database Migrations

Migrations auto-run on app startup. For manual control:

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Environment Variables

See `env.example` for all available options. Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `CORE_JWT_SECRET_KEY` | JWT signing secret |
| `WEBAPP_URL` | Frontend URL (for CORS) |
| `DEV_MODE` | Enable development features |

## Documentation

- [Backend (Core) Documentation](core/README.md)
- [Frontend (Webapp) Documentation](webapp/README.md)
- [AI Assistant Guide](CLAUDE.md)

## License

MIT
