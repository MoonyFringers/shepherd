# Plugins

This document describes the plugin model being introduced in Shepherd.

The current implementation scope is limited to:

- plugin descriptor format
- plugin inventory persisted in the main Shepherd config
- managed plugin installation directory layout
- plugin lifecycle commands for install, inspect, enable, disable, and remove

Runtime loading, command extension, completion extension, and factory/template
registration are introduced in later steps of the plugin rollout.

For the architectural rationale and staged implementation plan, see
[ADR 0004](decisions/0004-plugin-architecture-and-rollout-plan.md).

## Managed Plugin Layout

Plugins are not loaded from arbitrary filesystem paths.

Shepherd reserves a managed plugin root under the local Shepherd home:

```text
~/.shpd/plugins/<plugin-id>/
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

Capability flags must be real YAML booleans. String values such as `"false"` or
`"0"` are rejected during descriptor validation.

## Current Validation Rules

The descriptor parser validates:

- required metadata presence
- entrypoint presence
- capabilities as a mapping
- capability values as actual booleans

Invalid descriptors fail validation early, before runtime plugin loading is
introduced.

## Scope Of This Step

This documentation matches the current implementation step. At this stage,
Shepherd does not yet:

- import plugin Python entrypoints with `importlib`
- load plugin commands into the CLI
- load plugin completion providers
- register plugin factories or templates at runtime

Plugin archive installation and persisted inventory management are available
now. Runtime loading and extension points are added in follow-up PRs from the
plugin rollout plan.
