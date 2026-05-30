#!/usr/bin/env bash

echo "Removing all node_modules in subdirectories ..."
find . -type d -name "node_modules" -exec rm -rf {} +

echo "Removing root node_modules ..."
rm -rf node_modules

echo "Removing all dist directories in subdirectories ..."
find . -type d -name "dist" -exec rm -rf {} +
