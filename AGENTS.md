# AGENTS.md

This file provides guidance to people and AI agents working with code in
this repository.

## Project description

Shepherd is a CLI tool (`shepctl`) for provisioning and managing
reproducible development environments. It orchestrates services via
Docker Compose, with a plugin system for extensibility (CLI commands,
completions, environment/service templates, and remote storage
backends).

Shepherd Core Stack is dual-licensed under the
[GNU AGPL v3](LICENSE) and a
[proprietary commercial license](LICENSE-COMMERCIAL); every
contribution requires a signed CLA (see the `pr-prep` workflow).

## Design reference — read this first

- **`docs/decisions/CURRENT.md`** — snapshot of the currently-active
  decisions, organized by area. Start here; it saves reading the full
  ADR corpus end to end.
- `docs/decisions/README.md` — index and instructions for adding a new
  ADR (MADR format). Check for a relevant decision record before
  making significant design changes.

## Agent workflows

The agent-neutral workflows in
[`docs/agent-workflows/`](docs/agent-workflows/README.md) are mandatory
task guidance. Read the matching workflow before acting:

| Work | Workflow |
| --- | --- |
| Cut a release, bump version, publish a build | `release-process` |
| Build or modify a shepherd plugin | `plugin-authoring` |
| Commit, push, or open a pull request | `pr-prep` |
| Set up the dev environment, run tests/lint locally | `local-dev-testing` |
| Decide Claude Code vs Codex MCP routing for a task | `codex-task-routing` |

Claude wrappers under `.claude/` exist only for compatibility; the
documents above are authoritative.

## Tech stack

Python 3.12+, Click (CLI), Docker Compose (orchestration backend).

## Project structure & module organization

Core code lives in `src/`:

- CLI entrypoint: `src/shepctl.py` — a `ShepherdMng` composition root
  wires all managers together; `PluginRootGroup`/`PluginScopeGroup` are
  custom Click groups that inject plugin commands at runtime.
- `src/config/` — loads `~/.shpd.conf` (user preferences) and
  `shpd.yaml` (environment/service definitions); supports `${VAR}`
  substitution and `#{REF}` cross-config references.
- `src/environment/` — abstract `Environment` base class;
  `DockerComposeEnv` (in `src/docker/`) is the concrete implementation.
  Handles lifecycle (up/halt/reload), status rendering, probe-based
  health checks.
- `src/service/` — abstract `Service` base class; `DockerComposeSvc`
  (in `src/docker/`) is the concrete implementation. Handles container
  naming, logs, exec, status.
- `src/docker/` — generates and executes Docker Compose files, wraps
  compose command output.
- `src/plugin/` — `PluginMng` (discovery/install), `PluginRuntimeMng`
  (runtime loading via `importlib`, registry management). See the
  `plugin-authoring` workflow.
- `src/factory/` — `ShpdEnvironmentFactory`/`ShpdServiceFactory`
  dispatch to the correct backend (built-in or plugin-provided).
- `src/completion/` — `CompletionMng` delegates to per-domain providers
  (envs, services, plugins, probes).
- `src/installer/` — installer logic.
- `src/util/` — shared utilities.
- `src/tests/` — tests and fixtures.

Documentation lives in `docs/`. Helper and release scripts are in
`scripts/`. Runtime example configs are `shpd.yaml` and
`shpd.public-test.yaml`. Reference plugin examples are in
`examples/plugins/`.

## Common commands

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt -r src/requirements-dev.txt
pre-commit install
python3 src/shepctl.py --help  # verify entrypoint
```

```sh
pre-commit run --all-files
black src
isort src
cd src && pyright .
cd src && pytest
```

Full command reference, targeted test invocations, and the build
helper: `local-dev-testing` workflow.

## Tests

- pytest, run from `src/` (pythonpath/coverage config lives in
  `src/pyproject.toml`).
- Test files: `src/tests/test_*.py`; fixtures in `src/tests/fixtures/`.
- Markers: `env`, `svc`, `cfg`, `shpd`, `compl`, `docker`.

## Coding style & naming conventions

- Black + isort, 80-char line length (`src/pyproject.toml`).
- Pyright strict mode.
- `snake_case` functions/modules, `PascalCase` classes,
  `UPPER_SNAKE_CASE` constants.
- Follow existing package boundaries under `src/` rather than adding
  cross-cutting utilities ad hoc.

## Commits and PRs

Conventional Commits, `<type>/<short-kebab-description>` branch
naming, CLA sign-off gate on every PR. Full ritual: `pr-prep` workflow.
