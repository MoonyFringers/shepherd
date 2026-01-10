#!/bin/bash

# Release Automation Script for Shepherd
# Implements the protocol defined in docs/release-process.md

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RESET='\033[0m'

VERSION_FILE="src/version"
CHANGELOG_FILE="CHANGELOG.md"

# 1. Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}[ERROR]${RESET} Usage: $0 <version>"
    echo "Example: $0 1.2.0"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (simple regex for semver-ish)
if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}[ERROR]${RESET} Version must be in format X.Y.Z (e.g., 1.2.0)"
    exit 1
fi

echo -e "${BLUE}[INFO]${RESET} Preparing release for version: $NEW_VERSION"

# 2. Update Version File
echo -e "${BLUE}[INFO]${RESET} Updating $VERSION_FILE..."
echo "$NEW_VERSION" > "$VERSION_FILE"

# 3. Generate Changelog
echo -e "${BLUE}[INFO]${RESET} Generating changelog..."
if ! command -v git-cliff &> /dev/null; then
    echo -e "${RED}[ERROR]${RESET} git-cliff is not installed. Please install it first."
    exit 1
fi
# Generate changelog for the specific tag, outputting to CHANGELOG.md
git cliff --tag "$NEW_VERSION" --output "$CHANGELOG_FILE"

# 4. Commit Release
echo -e "${BLUE}[INFO]${RESET} Committing release artifacts..."
git add "$VERSION_FILE" "$CHANGELOG_FILE"
git commit -m "chore(release): prepare release $NEW_VERSION"

# 5. Tagging
echo -e "${BLUE}[INFO]${RESET} Tagging release..."
git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION"

echo -e "${GREEN}[SUCCESS]${RESET} Release prepared successfully!"
echo "Next steps:"
echo "  1. Review the changes: git show HEAD"
echo "  2. Push the changes and tag: git push origin main --tags"
