#!/usr/bin/env bash

echo "Removing __pycache__ ..."
find . -type d -name "__pycache__" -exec rm -rf {} +

echo "Removing .mypy_cache ..."
rm -rf .mypy_cache

echo "Removing .pytest_cache ..."
rm -rf .pytest_cache
rm -f .coverage 

echo "Removing .ruff_cache ..."
rm -rf .ruff_cache

echo "Removing dist ..."
rm -rf dist
