# Development

This guide covers the local setup and day-to-day commands for contributing to
Shepherd.

## Prerequisites

You need:

- Python 3.12+
- `pip`
- `venv`
- Git

On Debian-based systems:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git -y
```

## Initial Setup

Clone the repository and create a local virtual environment:

```bash
git clone git@github.com:MoonyFringers/shepherd.git
cd shepherd
python3 -m venv .venv
source .venv/bin/activate
```

Install project dependencies:

```bash
pip install --upgrade pip
pip install -r src/requirements.txt -r src/requirements-dev.txt
pre-commit install
```

Verify the CLI entrypoint:

```bash
python3 src/shepctl.py --help
```

## Project Layout

Core code lives in `src/`:

- `src/shepctl.py`: CLI entrypoint
- `src/config/`: configuration loading and validation
- `src/environment/`: environment orchestration and status rendering
- `src/service/`: service operations
- `src/docker/`: docker-compose integration
- `src/completion/`: shell completion support
- `src/installer/`: installer logic
- `src/util/`: shared utilities
- `src/tests/`: tests and fixtures

Documentation lives in `docs/`.

Sample `shpd.yaml` configurations live in `examples/`.

## Daily Commands

Run the full local quality pass:

```bash
pre-commit run --all-files
black src
isort src
cd src && pyright .
cd src && pytest
```

Run individual checks as needed:

```bash
black src
isort src
cd src && pyright .
cd src && pytest -k status
```

Notes:

- Run `pyright` from `src/` so it picks up the configuration in
  `src/pyproject.toml`.
- `pytest` is also intended to run from `src/`, where the configured
  `pythonpath` and coverage settings live.

## Style and Conventions

- Formatting: Black + isort
- Line length: 80
- Type checking: Pyright in strict mode
- Test files: `src/tests/test_*.py`
- Python naming:
  - functions/modules: `snake_case`
  - classes: `PascalCase`
  - constants: `UPPER_SNAKE_CASE`

Follow the existing package boundaries under `src/` instead of introducing
new cross-cutting utilities unnecessarily.

## Build Helper

The repository includes a PyInstaller-based build helper:

```bash
python3 src/build.py [--clean|--debug|--git|--version]
```

Common usage:

```bash
python3 src/build.py
python3 src/build.py --clean
python3 src/build.py --debug
python3 src/build.py --version
```

## Releasing

For release steps, changelog generation, and publishing artifacts, see
[Release Process](release-process.md).
