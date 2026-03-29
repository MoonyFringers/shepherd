# Hello Plugin

A minimal, installable Shepherd plugin that demonstrates every extension point
of the plugin API.

## What it demonstrates

| Extension point     | Where          | What it adds                         |
|---------------------|----------------|--------------------------------------|
| CLI command         | `commands.py`  | `shepctl hello greet [name]`         |
| Completion provider | `completion.py`| Dynamic completions for `hello` scope|
| Service factory     | `factories.py` | `echo-factory` (busybox echo service)|
| Environment factory | `factories.py` | `demo-env-factory` (demo environment)|
| Service template    | `plugin.yaml`  | `hello-plugin/echo`                  |
| Environment template| `plugin.yaml`  | `hello-plugin/demo`                  |

The entry point (`hello_plugin/main.py`) has inline comments explaining each
spec type, the callable convention for factories, the Protocol alternative for
completion providers, and the namespacing rule for factory IDs.

## Prerequisites

A working Shepherd development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt -r src/requirements-dev.txt
```

## Install and enable

```bash
# Install directly from the source directory (--force overwrites an existing copy)
python3 src/shepctl.py plugin install examples/plugins/hello-plugin --force

# Enable the plugin
python3 src/shepctl.py plugin enable hello-plugin

# Verify
python3 src/shepctl.py plugin get hello-plugin
```

## Usage

```bash
# New CLI command contributed by the plugin
python3 src/shepctl.py hello greet
python3 src/shepctl.py hello greet World

# List plugin-owned service and environment templates
python3 src/shepctl.py svc template list
python3 src/shepctl.py env template list
```

## Type checking

The plugin ships its own `pyrightconfig.json` that points at the shared `.venv`
and adds the Shepherd `src/` directory to the search path:

```bash
pyright --project examples/plugins/hello-plugin/pyrightconfig.json
```

This should report 0 errors in strict mode.

## Uninstall

```bash
python3 src/shepctl.py plugin disable hello-plugin
python3 src/shepctl.py plugin remove hello-plugin
```
