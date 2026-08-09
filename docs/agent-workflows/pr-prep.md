Commit and PR preparation
==========================

Fork workflow
--------------

`MoonyFringers/shepherd` uses a fork-per-developer model: clone your
personal fork, add the org repo as `upstream`.

```sh
git clone git@github.com:<you>/shepherd.git
git remote add upstream git@github.com:MoonyFringers/shepherd.git
```

Note: in this local checkout, `origin` and `upstream` are inverted from
that convention — `origin` points at `MoonyFringers/shepherd` and a
separate named remote (`giubacc`) points at the personal fork. Check
`git remote -v` before assuming which remote is which; don't rely on
the name alone.

Branch naming
--------------

`<type>/<short-kebab-description>`, where `<type>` is one of:

| Type       | Description                                      |
| ---------- | ------------------------------------------------ |
| `feature`  | New functionality or enhancements                |
| `bug`      | Bug fixes and corrections                        |
| `docs`     | Documentation updates                            |
| `test`     | Adding or updating tests                         |
| `refactor` | Code restructuring without functionality changes |

Example: `feature/probe-timeout`.

Commit format
--------------

- Conventional Commits: `feat(env): ...`, `fix(plugin): ...`,
  `docs: ...`. Scope is optional but encouraged when the change is
  domain-specific.
- Subject line concise and imperative, ~50 characters.
- Reference the related issue with `Fixes #N` / `Closes #N` /
  `Resolves #N` in the commit body or PR description — GitHub then
  auto-closes the issue on merge.
- A commit-message template is available at `docs/commit-template`; copy
  it to `~/.commit-template` and set `git config init.templateDir
  ~/.commit-template` to use it by default.
- No `Co-Authored-By` trailer (or similar attribution footer) for any
  AI agent, on any commit.

Before every commit
---------------------

```sh
pre-commit run --all-files
cd src && pytest
```

All hooks and tests must pass; fix source, not tests, on a mismatch.
Every patch must include tests covering the new or changed code —
manual verification alone (running a command by hand, checking a
container starts) doesn't survive the next refactor. See
`local-dev-testing` for detail.

CLA gate
---------

Shepherd is dual-licensed (AGPL-3.0-only + proprietary commercial,
[ADR-0005](../decisions/0005-dual-license-model.md)). Every PR is
gated by the CLA Assistant bot: it comments on the PR if the author
hasn't signed yet. To sign, read `CLA.md` and reply to the bot comment
with the exact phrase:

> I have read the CLA Document and I hereby sign the CLA

Your GitHub username is then recorded in `.github/cla_signatures.json`.
This is a one-time gate per contributor, not per PR — merges are
blocked until it's satisfied.

PR body
--------

Clear summary, linked issue (`Fixes #N`), and note any docs/tests
updated. Target `MoonyFringers/shepherd:main`. Merge only once CI and
the CLA check both pass.

See also
--------

`CONTRIBUTION_GUIDELINES.md` is the fuller human-onboarding version of
this document (fork setup walkthrough, Code of Conduct pointer,
contribution tips); this workflow is the agent-actionable distillation.
