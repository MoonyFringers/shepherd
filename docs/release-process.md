# Release Process

This document outlines the standard operating procedure for releasing new
versions of Shepherd.

## Prerequisites

- **git-cliff**: This tool is required for generating the changelog.
  - **Binary Download (Recommended)**: Download the pre-built binary from the
      [GitHub Releases page](https://github.com/orhun/git-cliff/releases) and add
      it to your PATH.
  - **Pip**: `pip install git-cliff` (convenient if you are already in a Python environment).
  - **Cargo**: `cargo install git-cliff` (if you have Rust installed).
  - **npm**: `npm install -g git-cliff` (if you have Node.js installed).
- **Push Access**: You need write access to the main repository to push tags.

## Automated Release Workflow

We provide a script to automate the tedious parts of the release process
(version bumping, changelog generation, tagging).

### 1. Prepare the Release

From the root of the repository:

```bash
# Usage: ./scripts/release.sh <version>
./scripts/release.sh 1.2.0
```

This script will:

1. Update the `src/version` file.
2. Generate/Update `CHANGELOG.md` using `git-cliff` configuration from
   `cliff.toml`.
3. Create a commit: `chore(release): prepare release 1.2.0`.
4. Create a git tag: `1.2.0`.

### 2. Verify

Always inspect the generated changes before pushing.

```bash
git show HEAD
```

Check that:

- The `src/version` contains the correct number.
- `CHANGELOG.md` looks correct and has the new section.

### 3. Publish

Once satisfied, push the commit and the tag to the upstream repository.

```bash
git push origin main --tags
```

This action will trigger the CI/CD pipeline (GitHub Actions) defined in
`.github/workflows/release.yaml`.

## Manual Process (Fallback)

If the script fails or you need manual control:

1. **Update Version**: Edit `src/version` with the new version string.

2. **Generate Changelog**:

   ```bash
   git cliff --tag 1.2.0 --output CHANGELOG.md
   ```

3. **Commit**:

   ```bash
   git add src/version CHANGELOG.md
   git commit -m "chore(release): prepare release 1.2.0"
   ```

4. **Tag**:

   ```bash
   git tag -a 1.2.0 -m "Release 1.2.0"
   ```

5. **Push**:

   ```bash
   git push origin main --tags
   ```
