---
name: fix-lint
description: Auto-fix all linting and formatting issues across the project
argument-hint: "[python|webapp]"
disable-model-invocation: true
---

Auto-fix all linting and formatting issues in the project.

## Scope

If `$ARGUMENTS` is provided, fix only that target:
- `python` → Python fixes only
- `webapp` → Webapp fixes only

If no argument, fix everything.

## Process

### Python fixes
1. Run `make fix-format` (ruff format)
2. Run `make fix-sort` (ruff import sorting)
3. Run `uv run ruff check --fix` (auto-fixable lint rules)
4. Run `make check-python` to verify. If mypy or remaining ruff issues exist, read the files and fix manually.

### Webapp fixes
1. Run `pnpm --filter webapp run check --write` (Biome auto-fix)
2. Run `make check-webapp` to verify. Fix any remaining issues manually.

## Final verification

After all fixes, run `make check` to confirm everything passes.
