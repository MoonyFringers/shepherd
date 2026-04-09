# Fragment demo configuration

This example demonstrates the `env_template_fragments` feature with two
cooperating plugins:

- **data-plugin** — the *fragment provider*: declares a key-value store
  service template and bundles it with its readiness probe, data volume, and
  network into a reusable `kv-base` fragment.
- **app-plugin** — the *fragment embedder*: depends on data-plugin and imports
  `data-plugin/kv-base` into its `demo` env_template, supplying the `kv_name`
  placeholder via a `with:` block.

## Prerequisites

Install both plugins from the `examples/plugins/fragment-demo/` directory:

```bash
shepctl plugin install ./examples/plugins/fragment-demo/data-plugin
shepctl plugin install ./examples/plugins/fragment-demo/app-plugin
```

## Usage

Point Shepherd at this configuration and start the `my-app` environment:

```bash
export SHPD_CONFIG=examples/configurations/fragment-demo/shpd.yaml
shepctl env start my-app
```

The resulting environment contains:

- a `kv` service (from the `data-plugin/kv-store` template, via the fragment)
- a `web` service (from the `app-plugin/web` template, declared inline)
- a `kv-ready` readiness probe
- a `kv_data` volume
- a shared `demo-net` bridge network
