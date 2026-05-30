---
name: new-endpoint
description: Scaffold a new FastAPI endpoint with model, router, and migration. Use when creating a new API resource.
argument-hint: "<entity-name>"
---

Scaffold a complete new API endpoint for the project following established patterns.

The entity name is: `$ARGUMENTS`

If no argument is provided, ask the user for the entity name and what fields it should have.

## Steps

### 1. Create the SQLModel model

Create `core/src/core/models/<entity_snake_case>.py` following the pattern in `core/src/core/models/user.py`:

- Import from `sqlmodel`, `sqlalchemy`, `uuid`, `datetime`
- Define the table model class with `SQLModel, table=True`
- Always include: `id` (UUID, primary key, `gen_random_uuid()`), `created_at`, `updated_at` with server defaults
- Use `Field(sa_column=Column(...))` for columns needing server defaults

### 2. Create the router

Create `core/src/core/routers/<entity_snake_case>.py` following the pattern in `core/src/core/routers/health.py`:

- Define Pydantic `BaseModel` classes for request/response schemas
- Create router with `APIRouter(prefix="/<entity-kebab-case>", tags=["<Entity Name>"])`
- Implement CRUD endpoints: `GET /` (list), `GET /{id}` (detail), `POST /` (create), `PUT /{id}` (update), `DELETE /{id}` (delete)
- Use `Annotated[AsyncSession, Depends(get_session)]` for database sessions
- Use `Annotated[User, Depends(get_current_user)]` for authenticated endpoints
- All handlers must be `async`

### 3. Register the router

- Add import and export in `core/src/core/routers/__init__.py`
- Add `app.include_router(<entity>_router)` in `core/src/core/main.py`

### 4. Create and apply migration

- Run `make db-migrate MSG="add <entity> table"`
- Review the generated migration file
- Add `updated_at` trigger if not auto-generated
- Run `make db-upgrade`

### 5. Run checks

- Run `make check-python` to verify code quality
- Fix any issues found

## Naming Conventions

- Model file: `snake_case.py` (e.g., `team_member.py`)
- Model class: `PascalCase` (e.g., `TeamMember`)
- Table name: `snake_case` (e.g., `team_member`)
- Router variable: `<entity>_router` (e.g., `team_member_router`)
- URL prefix: `kebab-case` (e.g., `/team-members`)
- Tag: Title case (e.g., `Team Members`)
