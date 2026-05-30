#!/usr/bin/env bash

set -e

# Define packages to update
PACKAGES=("webapp")

# Get the latest git tag
LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -z "$LATEST_TAG" ]; then
  echo "Error: No git tags found"
  exit 1
fi

# Remove the "v" prefix if present
NEW_VERSION="${LATEST_TAG#v}"

echo "Updating package versions to: $NEW_VERSION (from tag: $LATEST_TAG)"

# Cross-platform sed in-place edit
sedi() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "$@"
  else
    sed -i "$@"
  fi
}

# Update root package.json
echo "Updating root package.json..."
sedi "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" package.json

# Update package.json files in the workspace
echo "Updating workspace package.json files..."
for package in "${PACKAGES[@]}"; do
  while IFS= read -r -d '' file; do
    sedi "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$file"
  done < <(find "$package" -name "package.json" -type f -print0)
done

# Update pnpm-lock.yaml
echo "Updating pnpm-lock.yaml..."
pnpm install --no-frozen-lockfile

# Build git status check patterns
STATUS_PATTERNS=()
GIT_ADD_PATTERNS=()
for package in "${PACKAGES[@]}"; do
  if [ "$package" = "shared" ]; then
    STATUS_PATTERNS+=("$package/*/package.json")
    GIT_ADD_PATTERNS+=("$package/*/package.json")
  else
    STATUS_PATTERNS+=("$package/package.json")
    GIT_ADD_PATTERNS+=("$package/package.json")
  fi
done
# Add root package.json
STATUS_PATTERNS+=("package.json")
GIT_ADD_PATTERNS+=("package.json")
STATUS_PATTERNS+=("pnpm-lock.yaml")
GIT_ADD_PATTERNS+=("pnpm-lock.yaml")

# Check if there are changes
if [[ -n $(git status --porcelain "${STATUS_PATTERNS[@]}") ]]; then
  echo "Changes detected. Committing and pushing..."
  git add "${GIT_ADD_PATTERNS[@]}"
  git commit -m "chore: update package versions and lock file to $NEW_VERSION"
  git push origin main
  echo "Successfully updated and pushed package versions to $NEW_VERSION"
else
  echo "No changes to package.json or pnpm-lock.yaml"
fi