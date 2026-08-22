---
name: check
description: Run all code quality checks (Python + webapp) and auto-fix issues
argument-hint: "[python|webapp]"
disable-model-invocation: true
---

Run code quality checks for the project. All commands run from the project root.

## Scope

If `$ARGUMENTS` is provided, run checks only for that target:
- `python` → `make check-python`
- `webapp` → `make check-webapp`

If no argument is provided, run `make check` (all checks).

## Process

1. Run the appropriate make command(s) and capture output.
2. If all checks pass, report success.
3. If any checks fail:
   a. Parse the error output to identify the specific files and issues.
   b. For Python formatting issues: run `make fix-format` and `make fix-sort` to auto-fix.
   c. For Python lint issues (ruff): run `uv run ruff check --fix` first, then fix remaining issues manually.
   d. For Python type errors (mypy): read the failing files, understand the type issue, and fix manually.
   e. For webapp issues (Biome): run `pnpm --filter webapp run check --write` to auto-fix, then fix remaining issues manually.
   f. After fixing, re-run the original check command to verify all issues are resolved.
4. Repeat until all checks pass or report any issues that cannot be auto-fixed.

## Important Notes

- Python checks run on the host (not in Docker): `uv run ruff`, `uv run mypy`
- JS checks run on the host: `pnpm --filter webapp run check`
- Always run the full check again after fixes to catch cascading issues.
- For Biome, the `--write` flag auto-applies safe fixes (formatting + lint).
- Ruff is configured with 100 char line length and double quotes.
