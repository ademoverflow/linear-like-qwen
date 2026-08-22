---
name: migrate
description: Create and apply Alembic database migrations. Use when model changes need a migration.
argument-hint: "<migration-description>"
---

Guide through the full Alembic migration workflow for the project.

## Process

1. **Create migration**: Run `make db-migrate MSG="$ARGUMENTS"` to auto-generate a migration from model changes.
   - If `$ARGUMENTS` is empty, ask the user for a migration description.

2. **Review the migration**: Read the newly created file in `core/src/core/alembic/versions/` (the most recently modified `.py` file). Check for:
   - Correctness: Does `upgrade()` match the intended model changes?
   - Safety: Are there destructive operations (DROP TABLE, DROP COLUMN) that need confirmation?
   - Completeness: Does `downgrade()` properly reverse all changes?
   - Custom SQL: Does it need triggers (e.g., `updated_at` trigger)?

3. **Report findings**: Show the user the migration contents and flag any concerns.

4. **Apply migration**: Run `make db-upgrade` to apply the migration.

5. **Verify**: Run `make db-current` to confirm the migration was applied.

## Important Notes

- Migrations run inside the Docker core container.
- Migration files are at `core/src/core/alembic/versions/`.
- Models are in `core/src/core/models/` — ensure model changes are saved before generating.
- All tables should have `updated_at` triggers — check existing migrations for the pattern:
  ```sql
  CREATE TRIGGER updated_at_trigger BEFORE UPDATE ON <table>
  FOR EACH ROW EXECUTE PROCEDURE before_update_updated_at();
  ```
- If the migration looks wrong, delete the generated file and re-generate after fixing models.
