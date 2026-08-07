Local development and testing
==============================

Setup
-----

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt -r src/requirements-dev.txt
pre-commit install
python3 src/shepctl.py --help   # verify entrypoint
```

Daily commands
--------------

Run from the repo root unless noted:

```sh
pre-commit run --all-files
black src
isort src
```

Run `pyright` and `pytest` from `src/` — that is where
`src/pyproject.toml`'s configuration (pythonpath, coverage, strict
type-checking) lives:

```sh
cd src
pyright .
pytest
```

Targeted test runs:

```sh
cd src
pytest -k <pattern>                          # by keyword
pytest tests/test_config.py                  # single file
pytest tests/test_config.py::test_load_config  # single test
pytest -m cfg                                 # by marker
```

Markers: `cfg`, `env`, `svc`, `shpd`, `compl`, `docker`.

**Every patch must include tests that cover the new or changed code.**
Coverage reporting is configured (`--cov` in `src/pyproject.toml`,
`codecov.yml`), but it is currently `informational: true` — CI won't
block a drop in coverage. That is not license to skip tests: manual
verification (running a command by hand, checking a container comes
up) is not a substitute for a unit test that survives the next
refactor. Check the coverage delta for touched files
(`pytest --cov-report=term` output) before considering a change done,
same discipline as the sibling `numero-uno-backend` repo's Codecov
patch gate, just not yet CI-enforced here.

Build the binary
-----------------

```sh
python3 src/build.py [--clean|--debug|--git|--version]
```

Style
-----

- Black + isort, 80-char line length, configured in `src/pyproject.toml`.
- Pyright strict mode.
- `snake_case` functions/modules, `PascalCase` classes,
  `UPPER_SNAKE_CASE` constants.
- Follow existing package boundaries under `src/` rather than adding
  cross-cutting utilities ad hoc.

See also
--------

`docs/development.md` covers the same ground with more prose and links
to `docs/install.md` and `docs/release-process.md`; this document is
the terse, command-first version for agents.
