# Fragment Demo

A two-plugin Shepherd example demonstrating the `env_template_fragments`
feature: one plugin *provides* a fragment and another plugin *embeds* it.

## What it demonstrates

- **Fragment provider** (`data-plugin/plugin.yaml`) — declares
  `env_template_fragments` with `kv-base`
- **Declarative-only plugin** (`data-plugin/data_plugin/main.py`) — empty
  getters; the plugin's value lives entirely in `plugin.yaml`
- **Plugin dependency** (`app-plugin/plugin.yaml`) — `depends_on` with a
  PEP 440 version constraint
- **Fragment embedder** (`app-plugin/plugin.yaml`) — imports
  `data-plugin/kv-base` with a `with:` block
- **Placeholder injection** — `kv_name` is resolved at fragment merge time
- **Global placeholder fallthrough** — `${app_name}` inside a `with:` value
  passes through to Shepherd's standard `${VAR}` resolution

## Plugins

### data-plugin — the fragment provider

Registers a `kv-store` service template and bundles it into a `kv-base`
fragment that includes:

- the `kv` service (from `data-plugin/kv-store`)
- a `kv-ready` readiness probe
- a `kv_data` Docker volume
- a `demo-net` bridge network

The fragment exposes one placeholder: `${kv_name}`, which the embedder is
expected to fill via its `with:` block.

### app-plugin — the fragment embedder

Declares a hard dependency on `data-plugin >= 0.1.0`.  Its `demo`
env_template imports `data-plugin/kv-base` and sets:

```yaml
fragments:
  - id: data-plugin/kv-base
    with:
      kv_name: "${app_name}-store"
```

`${kv_name}` is resolved at merge time.  `${app_name}` is *not* listed in
`with:` — Shepherd leaves it in place and resolves it later through its
standard global `${VAR}` substitution pass.

The final `demo` environment contains:

- `kv` service (from the fragment)
- `web` service (declared inline in app-plugin)
- `kv-ready` probe, `kv_data` volume, `demo-net` network (from the fragment)

## Prerequisites

A working Shepherd development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt -r src/requirements-dev.txt
```

## Install and enable

```bash
# Install both plugins (order does not matter — Shepherd resolves load order)
python3 src/shepctl.py plugin install \
  examples/plugins/fragment-demo/data-plugin --force
python3 src/shepctl.py plugin install \
  examples/plugins/fragment-demo/app-plugin --force

python3 src/shepctl.py plugin enable data-plugin
python3 src/shepctl.py plugin enable app-plugin

# Verify both appear in the registry
python3 src/shepctl.py plugin get data-plugin
python3 src/shepctl.py plugin get app-plugin

# The fragment should be visible in the template list
python3 src/shepctl.py env template list
```

## Usage

```bash
# Start the demo environment using the configuration example
export SHPD_CONFIG=examples/configurations/fragment-demo/shpd.yaml
python3 src/shepctl.py env start my-app
```

## Type checking

Both plugins share the same `pyrightconfig.json` pattern as `hello-plugin`:

```bash
# Create pyrightconfig.json in each plugin directory (copy from hello-plugin)
# then run:
pyright --project examples/plugins/fragment-demo/data-plugin
pyright --project examples/plugins/fragment-demo/app-plugin
```
