Release process
================

Prerequisites
--------------

- **git-cliff**, for changelog generation: binary download (recommended,
  see the [GitHub Releases page](https://github.com/orhun/git-cliff/releases)),
  `pip install git-cliff`, `cargo install git-cliff`, or
  `npm install -g git-cliff`.
- Write access to `MoonyFringers/shepherd` to push tags.

Automated path
---------------

From the repo root:

```sh
./scripts/release.sh <version>   # e.g. ./scripts/release.sh 1.2.0
```

This updates `src/version`, regenerates `CHANGELOG.md` via `git-cliff`
(config: `cliff.toml`), commits
`chore(release): prepare release <version>`, and tags `<version>`.

Verify before pushing:

```sh
git show HEAD
```

Check `src/version` has the right number and `CHANGELOG.md`'s new
section looks correct.

Publish:

```sh
git push origin main --tags
```

Pushing the tag triggers `.github/workflows/release.yaml`.

Manual fallback
-----------------

If the script fails:

```sh
# 1. Edit src/version by hand to the new version string.

# 2. Generate the changelog entry.
git cliff --tag <version> --output CHANGELOG.md

# 3. Commit.
git add src/version CHANGELOG.md
git commit -m "chore(release): prepare release <version>"

# 4. Tag.
git tag -a <version> -m "Release <version>"

# 5. Push.
git push origin main --tags
```

See also
--------

`docs/release-process.md` is the fuller reference this workflow
distills; keep both in sync if the script or CI trigger changes.
