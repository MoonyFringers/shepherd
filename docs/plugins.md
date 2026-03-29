# Plugins

This document describes the plugin model being introduced in Shepherd.

The current implementation scope is limited to:

- plugin descriptor format
- plugin inventory persisted in the main Shepherd config
- managed plugin installation directory layout
- plugin lifecycle commands for install, inspect, enable, disable, and remove
- runtime loading of enabled plugins via `importlib`
- executable plugin commands injected into the CLI tree
- live plugin completion providers executed by the completion engine
- in-memory registries for plugin commands, completion providers, templates,
  and factories
- env and service flows resolving plugin-owned templates and factories at
  runtime

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
default_config:
  region: eu-west-1
env_templates:
  - tag: baseline
    factory: baseline-factory
    service_templates:
      - template: api
        tag: plugin-api
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
- `env_templates`
- `service_templates`

Capability flags must be real YAML booleans. String values such as `"false"` or
`"0"` are rejected during descriptor validation.

Plugin-owned env and service templates are now declared declaratively in
`plugin.yaml`, using the same schema shapes as the core Shepherd config. This
keeps template authoring data-driven. Python plugin code is only needed for
behavioral extensions like commands, completion, and factories.

## Current Validation Rules

The descriptor parser validates:

- required metadata presence
- entrypoint presence
- capabilities as a mapping
- capability values as actual booleans

Invalid descriptors fail validation early, before runtime plugin loading is
attempted.

## Runtime Loading

Enabled plugins are now loaded eagerly during normal startup:

1. Shepherd reads enabled plugin entries from the main config.
2. It derives each managed install directory from `~/.shpd/plugins/<plugin-id>/`.
3. It validates the installed `plugin.yaml`.
4. It imports the declared entrypoint with `importlib`.
5. It instantiates the root plugin object and registers the contributed
   runtime metadata.

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

The loader now builds in-memory registries for:

- loaded plugin metadata
- scope and verb contributions
- completion providers
- environment templates
- service templates
- environment factories
- service factories

Template and factory ids are canonicalized under the plugin namespace:

- templates: `plugin-id/template-id`
- factories: `plugin-id/factory-id`

Descriptor-declared template tags are loaded as local ids like `baseline` or
`api`, then canonicalized at runtime to:

- templates: `plugin-id/template-id`
- factories: `plugin-id/factory-id`

These registries are validated and populated at startup. Env and service
commands then resolve namespaced template and factory ids through them.

## Runtime Command Wiring

Plugin command contributions are now executable.

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

Plugin completion providers are now executed by the shared completion engine.

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

## Plugin API Types

The public plugin API is fully typed.  All types
below are importable from the `plugin` package.

### Spec types

| Class                  | Purpose                                           |
|------------------------|---------------------------------------------------|
| `PluginCommandSpec`    | Declares a scope + verb + Click command           |
| `PluginCompletionSpec` | Declares a completion provider for a scope        |
| `PluginEnvFactorySpec` | Declares an environment factory with a local id   |
| `PluginSvcFactorySpec` | Declares a service factory with a local id        |

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
    PluginSvcFactorySpec,
    ShepherdPlugin,
    SvcFactoryProvider,
)
```

## Example Plugin

A complete, installable reference plugin lives at
[`examples/plugins/hello-plugin/`](../examples/plugins/hello-plugin/).

It demonstrates all four extension points (commands, completion, service
factories, environment factories) and includes inline comments explaining each
spec type and the factory callable convention.

See [`examples/plugins/hello-plugin/README.md`](../examples/plugins/hello-plugin/README.md)
for install and usage instructions.

## Scope Of This Step

This documentation matches the current implementation step. At this stage,
Shepherd now does:

- execute plugin-owned environment factories through `env add` and normal env
  rehydration
- execute plugin-owned service factories through `svc add` and normal service
  rehydration
- resolve plugin-owned templates from canonical namespaced ids like
  `runtime-plugin/baseline`
- surface plugin-owned env and svc templates through the built-in completion
  managers
- copy plugin-owned service template assets from the installed plugin tree
  during environment realization

Plugin archive installation, persisted inventory management, runtime loader
bootstrap, command wiring, completion execution, and template/factory
consumption are available now. A later rollout step can still align more core
behavior behind the same plugin abstraction.
