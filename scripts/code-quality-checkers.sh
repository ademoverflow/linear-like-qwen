#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e 

# Activate virtualenv if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtualenv ..."
    source .venv/bin/activate
fi

# Remove .mypy_cache if it exists
if [ -d ".mypy_cache" ]; then
    echo "Removing .mypy_cache ..."
    rm -rf .mypy_cache
fi

# Remove .ruff_cache if it exists
if [ -d ".ruff_cache" ]; then
    echo "Removing .ruff_cache ..."
    rm -rf .ruff_cache
fi


# Run code quality checkers with poe:
echo "-- Running check format ..."
poe check_format
echo "-- Running check lint ..."
poe check_lint
echo "-- Running check sort ..."
poe check_sort
echo "-- Running check types ..."
poe type_check
echo "-- Running check types tests ..."
poe type_check