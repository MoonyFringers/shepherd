# Plugins

This document describes the Shepherd plugin model.

The current implementation covers:

- plugin descriptor format
- plugin inventory persisted in the main Shepherd config
- managed plugin installation directory layout
- plugin lifecycle commands for install, inspect, enable, disable, and remove
- runtime loading of enabled plugins via `importlib`, ordered by dependency
  graph
- executable plugin commands injected into the CLI tree
- live plugin completion providers executed by the completion engine
- in-memory registries for plugin commands, completion providers, templates,
  factories, and env_template_fragments
- env and service flows resolving plugin-owned templates and factories at
  runtime
- env_template_fragments for reusable, composable environment blocks
- plugin dependency declarations with PEP 440 version constraints

For the architectural rationale and staged implementation plan, see
[ADR 0004](decisions/0004-plugin-architecture-and-rollout-plan.md).

## Managed Plugin Layout

Plugins are not loaded from arbitrary filesystem paths.

Shepherd reserves a managed plugin root under the local Shepherd home:

```text
~/.shpd/plugins/<plugin-id>/
```

Plugin-owned service template assets are resolved from the installed plugin
directory using this convention:

```text
~/.shpd/plugins/<plugin-id>/templates/svcs/<template-id>/
```

The install directory is derived from the managed root and the plugin id. It is
not persisted as a free-form path in the main config.

This keeps plugin discovery deterministic and avoids config drift caused by
external paths moving or disappearing.

## Plugin Lifecycle Commands

The current CLI exposes plugin inventory management under the `plugin` scope:

- `shepctl plugin list`
- `shepctl plugin get <plugin-id>`
- `shepctl plugin install <archive>`
- `shepctl plugin enable <plugin-id>`
- `shepctl plugin disable <plugin-id>`
- `shepctl plugin remove <plugin-id>`

These commands operate on the persisted plugin inventory in the main config and
on the managed plugin root under `~/.shpd/plugins/`.

## Plugin Inventory In Config

The main Shepherd config persists the plugin inventory and state.

Example:

```yaml
plugins:
  - id: acme
    enabled: true
    version: 1.2.3
    config:
      region: eu-west-1
      enabled_feature: true
```

Fields:

- `id`: stable plugin identifier
- `enabled`: whether the plugin should be loaded at startup
- `version`: installed plugin version
- `config`: optional plugin-specific configuration stored in the main config

`enabled` follows the same bool-like config handling used by other Shepherd
config fields. YAML booleans are normalized, and placeholders such as
`${PLUGIN_ENABLED}` are preserved until resolution time.

## Plugin Descriptor

Each installed plugin ships a descriptor that defines its metadata and
entrypoint. The descriptor file name is currently fixed to `plugin.yaml`.

Example:

```yaml
id: acme
name: Acme Plugin
version: 1.2.3
plugin_api_version: 1
description: Extra envs and services for Acme stacks
entrypoint:
  module: plugin.main
  class: AcmePlugin
capabilities:
  templates: true
  commands: true
  completion: true
  env_factories: true
  svc_factories: true
  remote_backends: true
default_config:
  region: eu-west-1
depends_on:
  - id: base-plugin
    version: ">=1.0.0"
env_template_fragments:
  - tag: db-bundle
    service_template:
      template: api
      tag: db
    probes:
      - tag: db-ready
        container:
          tag: db-probe
          image: busybox:stable-glibc
          networks: []
        script: "sh -c 'sleep 1'"
    volumes:
      - tag: db_data
        external: false
        driver: local
    networks: []
env_templates:
  - tag: baseline
    factory: baseline-factory
    service_templates:
      - template: api
        tag: plugin-api
    fragments:
      - id: base-plugin/pg-bundle
        with:
          db_name: acme
service_templates:
  - tag: api
    factory: api-factory
    containers:
      - image: busybox:stable-glibc
        tag: app
```

Required fields:

- `id`
- `name`
- `version`
- `plugin_api_version`
- `entrypoint.module`
- `entrypoint.class`

Optional fields:

- `description`
- `capabilities`
- `default_config`
- `depends_on`
- `env_template_fragments`
- `env_templates`
- `service_templates`

Capability flags must be real YAML booleans. String values such as `"false"` or
`"0"` are rejected during descriptor validation.

Plugin-owned env and service templates are declared declaratively in
`plugin.yaml`, using the same schema shapes as the core Shepherd config. This
keeps template authoring data-driven. Python plugin code is only needed for
behavioral extensions like commands, completion, and factories.

## Plugin Dependencies

A plugin may declare hard dependencies on other plugins using `depends_on`:

```yaml
depends_on:
  - id: base-plugin
    version: ">=1.0.0"
  - id: auth-plugin
    version: ">=2.1.0,<3.0.0"
```

Each entry requires:

- `id` — the stable identifier of the required plugin
- `version` — a PEP 440 version specifier (optional; omit to accept any version)

Shepherd validates all constraints at startup, before any plugin code runs:

- If a declared dependency is not installed and enabled, startup fails hard.
- If the installed version does not satisfy the specifier, startup fails hard.
- If a dependency cycle is detected, startup fails hard.

Plugins are loaded in topological order — dependencies always load before the
plugins that declare them. This guarantees that a plugin's fragments and
templates are already registered when dependent plugins are processed.

## Environment Template Fragments

Fragments bundle a service, its readiness probes, volumes, and networks into
a named, reusable unit that other plugins or the core config can import.

### Declaring a fragment

```yaml
env_template_fragments:
  - tag: db-bundle
    service_template:
      template: api      # local id — auto-namespaced to plugin-id/api
      tag: db            # instance tag used in the merged environment
    probes:
      - tag: db-ready
        container:
          tag: db-probe
          image: busybox:stable-glibc
          networks:
            - demo-net
        script: "sh -c 'sleep 1'"
    volumes:
      - tag: db_data
        external: false
        driver: local
    networks:
      - tag: demo-net
        external: false
        driver: bridge
```

Registered under the namespaced id `plugin-id/db-bundle`.

Fragments may use `${KEY}` placeholders. Embedders supply values for them
through the `with:` block at import time (see below).

### Importing a fragment

Any `env_template` — in a plugin descriptor or in the core `shpd.yaml` —
can import fragments via the `fragments:` list:

```yaml
env_templates:
  - tag: demo
    factory: docker-compose
    fragments:
      - id: acme/db-bundle          # namespaced fragment id
        with:
          db_name: myapp            # resolves ${db_name} inside the fragment
    service_templates:
      - template: web
        tag: web
    probes: []
    networks: []
    volumes: []
```

Fragment merge semantics:

- Inline `service_templates` are collected first, then fragment services are
  appended in declaration order.
- Each fragment contributes its service, probes, volumes, and networks
  additively.
- Duplicate service instance `tag` values across fragments or between a
  fragment and an inline service_template cause a hard startup failure. Probe,
  volume, and network tags are merged additively without conflict detection.
- `${KEY}` placeholders in fragment content are substituted from `with:`
  values at merge time. Any placeholder not covered by `with:` passes through
  to Shepherd's standard global `${VAR}` resolution.
- `#{ref.path}` object references are never touched during fragment merge;
  they resolve through the standard config reference pass.

### Declaring a core-config fragment

Fragments may also be declared in the main `shpd.yaml`, not only in plugin
descriptors:

```yaml
env_template_fragments:
  - tag: worker-base
    service_template:
      template: worker
      tag: job
    probes:
      - tag: job-ready
        container:
          tag: job-probe
          image: busybox:stable-glibc
          networks:
            - default
        script: "sh -c 'echo ${job_name} && sleep 1'"
    volumes:
      - tag: job_data
        external: false
        driver: local
    networks:
      - tag: default
        external: false
        driver: bridge

env_templates:
  - tag: demo
    factory: docker-compose
    fragments:
      - id: worker-base
        with:
          job_name: my-job
    service_templates: []
    probes: []
    networks: []
    volumes: []
```

Core-config fragments are referenced by their plain `tag` (no namespace
prefix). Plugin-provided fragments are referenced as `plugin-id/tag`.

## Current Validation Rules

The descriptor parser validates:

- required metadata presence
- entrypoint presence
- capabilities as a mapping
- capability values as actual booleans
- `depends_on` as a list
- `env_template_fragments` as a list
- fragment tags do not contain `/` (reserved for namespacing)
- no duplicate fragment tags within the same plugin

Invalid descriptors fail validation early, before runtime plugin loading is
attempted.

## Runtime Loading

Enabled plugins are loaded eagerly during normal startup:

1. Shepherd reads enabled plugin entries from the main config.
2. It derives each managed install directory from `~/.shpd/plugins/<plugin-id>/`.
3. It validates the installed `plugin.yaml` for every enabled plugin.
4. It resolves load order by topological sort of the `depends_on` graph;
   any cycle or unsatisfied dependency causes a hard failure before import.
5. It imports each plugin entrypoint with `importlib` in dependency order.
6. It instantiates the root plugin object and registers the contributed
   runtime metadata (templates, fragments, factories, commands, completions).

Normal commands fail fast if an enabled plugin is missing, invalid, or cannot
be imported.

The `plugin` management scope keeps a safe bootstrap path and does not import
enabled external plugins before running:

- `shepctl plugin list`
- `shepctl plugin get <plugin-id>`
- `shepctl plugin install <archive>`
- `shepctl plugin enable <plugin-id>`
- `shepctl plugin disable <plugin-id>`
- `shepctl plugin remove <plugin-id>`

This keeps recovery commands available even if one enabled plugin is broken.

## Runtime Registries

The loader builds in-memory registries for:

- loaded plugin metadata
- scope and verb contributions
- completion providers
- environment templates
- service templates
- environment factories
- service factories
- environment template fragments
- remote backend transports

Template, factory, and fragment ids are canonicalized under the plugin
namespace at registration time:

- templates: `plugin-id/template-id`
- factories: `plugin-id/factory-id`
- fragments: `plugin-id/fragment-tag`

Service template references inside a fragment's `service_template.template`
field are also auto-namespaced from their local id to `plugin-id/local-id`
during registration. Use the local id inside `plugin.yaml`; Shepherd expands
it automatically.

These registries are validated and populated at startup. Env and service
commands then resolve namespaced template and factory ids through them.

## Runtime Command Wiring

Plugin command contributions are executable.

Each `PluginCommandSpec` declares:

- the target `scope`
- the target `verb`
- a ready-to-register Click command object

At startup Shepherd validates that:

- the Click command exists
- the Click command name matches the declared `verb`
- the command does not collide with a core command
- the command does not collide with another plugin command

If a plugin contributes a new top-level scope, Shepherd exposes it as a normal
CLI scope. If a plugin contributes a verb under an existing scope, Shepherd
extends that scope in place.

Examples:

- `shepctl observability tail`
- `shepctl env doctor`

## Runtime Completion Wiring

Plugin completion providers are executed by the shared completion engine.

Each `PluginCompletionSpec` targets one scope and provides a callable with the
signature `f(args: list[str]) -> list[str]`.  If you prefer a class-based
provider, implement the `CompletionProvider` protocol and pass the bound method:

```python
PluginCompletionSpec(scope="myscope", provider=my_obj.get_completions)
```

Completion results are merged with the built-in completion managers for the
same scope. This allows plugins to:

- complete verbs under plugin-owned scopes
- complete values for plugin-added verbs under existing scopes
- return dynamic values computed in Python at completion time

## Plugin Context

Every plugin receives a `PluginContext` injected through its constructor.
It provides typed, stable access to the Shepherd core managers without
importing internal concrete classes.

```python
from plugin import PluginContext, ShepherdPlugin

class MyPlugin(ShepherdPlugin):
    def __init__(self, context: PluginContext) -> None:
        super().__init__(context)
        # self.context is now available in all contribution getters
        # and in any Click command handler that closes over it.
```

`PluginContext` has four fields:

- `config: PluginConfigView` — always set; provides read access to
  environments, templates, and plugin metadata.
- `environment: PluginEnvironmentView | None` — set after the full CLI
  bootstrap; exposes environment lifecycle operations.
- `service: PluginServiceView | None` — set after the full CLI bootstrap;
  exposes service operations.
- `remote: PluginRemoteView | None` — set after the full CLI bootstrap;
  exposes lightweight index queries for configured remotes.

`environment`, `service`, and `remote` are `None` only during the Click
command resolution phase (tab completion).  By the time any command handler
executes they are always populated.

### Available operations

`PluginConfigView` exposes: `get_environments`, `get_active_environment`,
`get_environment`, `get_environment_templates`, `get_service_templates`,
`get_plugin`, `get_plugin_dir`.

`PluginEnvironmentView` exposes: `list_envs`, `describe_env`,
`get_environment_from_tag`, `add_env`, `add_service`, `delete_env`,
`start_env`, `stop_env`, `status_env`.

`PluginServiceView` exposes: `get_service`, `describe_svc`, `build_svc`,
`start_svc`, `stop_svc`, `reload_svc`, `logs_svc`, `shell_svc`,
`render_svc`.

`PluginRemoteView` exposes: `list_envs`, `list_snapshots`.

All four are `@runtime_checkable` Protocols satisfied structurally by the
concrete managers — plugin authors can mock them in unit tests without
any Shepherd-specific fixtures.

## Plugin API Types

The public plugin API is fully typed.  All types
below are importable from the `plugin` package.

### Spec types

| Class | Purpose |
| --- | --- |
| `PluginCommandSpec` | Declares a scope + verb + Click command |
| `PluginCompletionSpec` | Declares a completion provider for a scope |
| `PluginEnvFactorySpec` | Declares an environment factory with a local id |
| `PluginSvcFactorySpec` | Declares a service factory with a local id |
| `PluginRemoteBackendSpec` | Declares a remote transport with a `type_id` |

### Provider type aliases

`CompletionProviderType`
: `Callable[[list[str]], list[str]]`
  or `CompletionProvider`

`SvcFactoryProvider`
: `ServiceFactory` instance
  **or**
  `Callable[[ConfigMng], ServiceFactory]`

`EnvFactoryProvider`
: `EnvironmentFactory` instance
  **or**
  `Callable[[ConfigMng, ServiceFactory, dict | None],
            EnvironmentFactory]`

`RemoteBackendProvider`
: `RemoteBackend` instance
  **or**
  `Callable[[RemoteCfg], RemoteBackend]`

The most common pattern is to pass the **class** of your factory as the
provider.  Shepherd instantiates it at runtime with the correct arguments:

- service factories: `MyServiceFactory(configMng)`
- environment factories: `MyEnvironmentFactory(configMng, svc_factory, cli_flags)`

### `CompletionProvider` protocol

```python
class CompletionProvider(Protocol):
    def get_completions(self, args: list[str]) -> list[str]: ...
```

`@runtime_checkable`, so you can pass a class instance directly to
`CompletionProviderType`-typed arguments.

### Quick import reference

```python
from plugin import (
    CompletionProvider,
    CompletionProviderType,
    EnvFactoryProvider,
    PluginCommandSpec,
    PluginCompletionSpec,
    PluginEnvFactorySpec,
    PluginRemoteBackendSpec,
    PluginRemoteView,
    PluginSvcFactorySpec,
    RemoteBackendProvider,
    ShepherdPlugin,
    SvcFactoryProvider,
)
```

## Plugin-Contributed Remote Backends

Plugins can register new remote storage transports — S3, Azure Blob, GCS,
or any object store with read/write/list semantics — without modifying core
Shepherd code. For the built-in FTP and SFTP transports, their configuration
reference and the remote storage layout are documented in
[docs/remote.md](remote.md).

`RemoteMng._build_backend()` checks the built-in FTP and SFTP transports
first, then delegates to the plugin registry.  The dispatch pattern is
identical to the one used for environment and service factories.

### Descriptor capability flag

Declare `remote_backends: true` under `capabilities` in your `plugin.yaml`:

```yaml
capabilities:
  remote_backends: true
```

### Implementing `RemoteBackend`

Subclass `RemoteBackend` (importable from `remote`) and implement its six
abstract methods:

- **`exists(path: str) -> bool`** — check whether *path* exists.
- **`upload(path: str, data: bytes) -> None`** — write *data* to *path*,
  creating parents as needed.
- **`download(path: str) -> bytes`** — return the full contents of *path*.
- **`list_prefix(prefix: str) -> list[str]`** — return the leaf names of
  all objects whose key starts with *prefix/*.
  Example: `list_prefix("chunks/ab")` → `["ab3f1c9d...", "ab7e2a11..."]`.
- **`delete(path: str) -> None`** — delete *path* from the remote.
- **`close() -> None`** — release connections or resources.

`RemoteBackend` provides `__enter__` / `__exit__` so instances can be used
as context managers — the runtime always opens the backend inside a `with`
block, so `close()` is guaranteed to be called.

Plugin-specific connection parameters (bucket name, region, access keys,
etc.) live in the `properties` mapping of `RemoteCfg`.  Core Shepherd does
not validate this mapping, leaving it entirely to the plugin.

### Registering with `PluginRemoteBackendSpec`

Override `get_remote_backends()` in your plugin class and return one spec
per transport type:

```python
from plugin import ShepherdPlugin, PluginRemoteBackendSpec
from remote import RemoteBackend
from config.config import RemoteCfg


class MyS3Backend(RemoteBackend):
    def __init__(self, cfg: RemoteCfg) -> None:
        import boto3  # type: ignore[import]
        self._client = boto3.client(
            "s3",
            region_name=cfg.properties.get("region", "us-east-1"),
        )
        self._bucket = cfg.properties["bucket"]
        self._root = cfg.root_path.rstrip("/")

    def _key(self, path: str) -> str:
        return f"{self._root}/{path}"

    def exists(self, path: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(path))
            return True
        except self._client.exceptions.ClientError:
            return False

    def upload(self, path: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=self._key(path), Body=data
        )

    def download(self, path: str) -> bytes:
        resp = self._client.get_object(
            Bucket=self._bucket, Key=self._key(path)
        )
        return resp["Body"].read()

    def list_prefix(self, prefix: str) -> list[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        key_prefix = f"{self._root}/{prefix.rstrip('/')}/"
        results: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=key_prefix):
            for obj in page.get("Contents", []):
                leaf = obj["Key"][len(key_prefix):]
                if "/" not in leaf and leaf:
                    results.append(leaf)
        return results

    def delete(self, path: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=self._key(path))

    def close(self) -> None:
        pass  # boto3 sessions are stateless


class MyS3Plugin(ShepherdPlugin):
    def get_remote_backends(self):
        return [PluginRemoteBackendSpec(type_id="s3", provider=MyS3Backend)]
```

`type_id` is matched against the `type` field of each `remote` entry in
`~/.shpd.conf`.  It must not collide with the built-in identifiers `"ftp"`
and `"sftp"` — Shepherd rejects any plugin that tries to claim them.

### Remote config entry for a plugin transport

Once the plugin is installed and enabled, add a remote entry that sets
`type` to your `type_id` and places plugin-specific parameters in the
`properties` mapping:

```yaml
remotes:
  - name: prod-s3
    type: s3
    host: s3.amazonaws.com
    root_path: /shepherd
    properties:
      bucket: my-shepherd-bucket
      region: eu-west-1
```

Standard remote fields (`host`, `root_path`, `user`, `password`,
`identity_file`, chunk tuning, local cache settings) work exactly as they
do for FTP and SFTP entries.  `${VAR}` placeholders in any field are
resolved at runtime via the existing `Resolvable` mechanism, so credentials
do not need to be hard-coded.

### Accessing remote data from a plugin command

`PluginContext.remote` is a `PluginRemoteView` that exposes lightweight
index queries.  Use it in command handlers to report snapshot state or
drive cross-remote operations:

```python
class MyPlugin(ShepherdPlugin):
    def get_commands(self):
        import click
        from plugin import PluginCommandSpec

        @click.command("remote-summary")
        def remote_summary():
            """Print a quick summary of the default remote."""
            remote_cfg, catalogue = self.context.remote.list_envs()
            for env_name, entry in catalogue.environments.items():
                click.echo(
                    f"{env_name}: {entry.snapshot_count} snapshot(s) "
                    f"on {remote_cfg.name}"
                )

        return [PluginCommandSpec(scope="remote", verb="remote-summary",
                                  command=remote_summary)]
```

`list_envs(remote_name=None)` returns `(RemoteCfg, IndexCatalogue)`.
`list_snapshots(env_name, remote_name=None)` returns
`(RemoteCfg, list[SnapshotManifest])`.

## Example Plugins

### hello-plugin — all extension points

A complete, installable reference plugin lives at
[`examples/plugins/hello-plugin/`](../examples/plugins/hello-plugin/).

It demonstrates all four extension points (commands, completion, service
factories, environment factories) and includes inline comments explaining each
spec type and the factory callable convention.

See [`examples/plugins/hello-plugin/README.md`](../examples/plugins/hello-plugin/README.md)
for install and usage instructions.

### fragment-demo — fragments and plugin dependencies

A two-plugin example lives at
[`examples/plugins/fragment-demo/`](../examples/plugins/fragment-demo/).

It demonstrates:

- a *provider* plugin (`data-plugin`) that declares an `env_template_fragment`
  with `${placeholder}` variables
- an *embedder* plugin (`app-plugin`) that declares `depends_on` and imports
  the fragment with a `with:` block to supply placeholder values

A matching configuration example lives at
[`examples/configurations/fragment-demo/`](../examples/configurations/fragment-demo/).

See [`examples/plugins/fragment-demo/README.md`](../examples/plugins/fragment-demo/README.md)
for install and usage instructions.
