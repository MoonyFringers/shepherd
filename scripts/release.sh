#!/bin/bash

# Release Automation Script for Shepherd
# Implements the protocol defined in docs/release-process.md

set -e

VERSION_FILE="src/version"
CHANGELOG_FILE="CHANGELOG.md"

# 1. Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.2.0"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (simple regex for semver-ish)
if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 1.2.0)"
    exit 1
fi

echo "🚀 Preparing release for version: $NEW_VERSION"

# 2. Update Version File
echo "📝 Updating $VERSION_FILE..."
echo "$NEW_VERSION" > "$VERSION_FILE"

# 3. Generate Changelog
echo "📖 Generating changelog..."
if ! command -v git-cliff &> /dev/null; then
    echo "Error: git-cliff is not installed. Please install it first."
    exit 1
fi
# Generate changelog for the specific tag, outputting to CHANGELOG.md
git cliff --tag "$NEW_VERSION" --output "$CHANGELOG_FILE"

# 4. Commit Release
echo "💾 Committing release artifacts..."
git add "$VERSION_FILE" "$CHANGELOG_FILE"
git commit -m "chore(release): prepare release $NEW_VERSION"

# 5. Tagging
echo "🏷️  Tagging release..."
git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION"

echo "✅ Release prepared successfully!"
echo "Next steps:"
echo "  1. Review the changes: git show HEAD"
echo "  2. Push the changes and tag: git push origin main --tags"
