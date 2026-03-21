---
status: "accepted"
date: 2026-03-21
decision-makers:
  - '@giubacc'
consulted:
  - '@luca-c-xcv'
  - '@feed3r'
---

# Shepherd Plugin Architecture and Rollout Plan

## Context and Problem Statement

Shepherd is ready to introduce plugins, but the current implementation is
still organized around a static CLI, hardcoded factory dispatch, and core-owned
template catalogs in the main config.

We need to lock the target plugin architecture before implementation starts,
and we need a rollout plan that keeps the work split into small, reviewable
changes with logically consistent commits and PRs.

## Decision Drivers

* Plugins must extend Shepherd in a first-class way, not as ad hoc hooks.
* The plugin system must remain understandable to users and maintainers.
* CLI shape must scale to external extensions without increasing ambiguity.
* Template, factory, command, and completion ownership must be explicit.
* Plugin installation must be controlled by Shepherd, not arbitrary paths.
* The implementation should be delivered in small steps with low regression
  risk.

## Considered Options

* Keep the current `verb scope` CLI and add plugins around it.
* Refactor the CLI to `scope verb` first, then build plugins on top.
* Build a plugin system that copies plugin templates into the main config.
* Build a plugin system with plugin-owned runtime registries.

## Decision Outcome

Chosen options:

* Refactor the CLI to `scope verb` before plugin work starts.
* Build a plugin system around plugin-owned registries for templates,
  factories, commands, and completion.

These choices give Shepherd a clearer command tree, reduce collision risk, and
let plugins remain self-contained across install, enable, disable, upgrade,
and removal operations.

### Architecture

#### CLI Model

The target CLI model is `scope verb [args] [opts]`.

Examples:

* `shepctl env get`
* `shepctl env add`
* `shepctl svc get`
* `shepctl plugin install`

Plugin functional commands will follow the same model. A plugin may:

* add a new top-level scope if the name is unused
* add new verbs under an existing scope if the verb name is unused there

Core scopes and verbs are reserved. Any core/plugin or plugin/plugin collision
is a startup error.

#### Plugin Packaging and Installation

Plugins are distributed as `.tar.gz` archives containing:

* Python code
* a YAML descriptor
* optionally default config and bundled templates/resources

Plugins are installed only under a Shepherd-managed plugin root, for example:

* `~/.shpd/plugins/<plugin-id>/`

Config must not reference arbitrary external plugin paths.

#### Plugin Descriptor

The plugin descriptor is the authoritative install-time manifest.

Required fields:

* `id`
* `name`
* `version`
* `plugin_api_version`
* `entrypoint.module`
* `entrypoint.class`

Optional fields:

* `description`
* `capabilities`
* `default_config`

Illustrative shape:

```yaml
id: acme
name: Acme Plugin
version: 1.2.0
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

#### Config Model

The main Shepherd config remains the source of truth for installed plugins.
It persists plugin inventory and state, including disabled plugins.

Illustrative shape:

```yaml
plugins:
  - id: acme
    enabled: true
    version: 1.2.0
    config:
      region: eu-west-1
```

Rules:

* `plugins` live in the main config
* `enabled` controls startup loading
* the on-disk plugin directory is derived from the managed plugin root plus
  `id`, not persisted as an arbitrary path
* plugin-specific `config` is supported from v1
* `default_config` is copied into the plugin config block at install time if
  no config exists yet
* after install, main config is authoritative

#### Loading Model

Enabled plugins are loaded eagerly at startup for normal operational
commands.

Bootstrap flow:

1. Shepherd reads configured plugins from the main config.
2. Shepherd loads and validates each descriptor from the managed plugin root.
3. Shepherd imports the configured entrypoint via `importlib`.
4. Shepherd registers contributed scopes, verbs, completion providers,
   templates, and factories.
5. Shepherd aborts startup on any validation, import, or registration error.

Core plugin-management commands use a plugin-safe bootstrap path that reads
config and managed plugin directories directly, without importing enabled
plugins first. This recovery path must keep at least the following commands
available even if an enabled plugin is broken:

* `shepctl plugin list`
* `shepctl plugin get <plugin-id>`
* `shepctl plugin disable <plugin-id>`
* `shepctl plugin remove <plugin-id>`
* `shepctl plugin install <archive>`

Partial startup is not supported in v1 for normal operational commands.

#### Plugin Interface Model

There is one root plugin entrypoint interface, `ShepherdPlugin`, and narrower
contribution interfaces for what the plugin provides.

Expected contribution areas:

* commands
* completion
* environment factories
* service factories
* templates
* plugin metadata/default config

This preserves the abstract-factory design while keeping each contribution
typed and isolated.

#### Template and Factory Ownership

Templates remain owned by the plugin that ships them. They are not copied into
the core template arrays in the main config.

Instead, Shepherd builds unified runtime registries from:

* built-in core contributions
* external plugin contributions

Canonical ids are namespaced:

* templates: `plugin-id/template-id`
* factories: `plugin-id/factory-id`

Persisted environment and service config must store canonical namespaced ids.

#### Completion Model

Completion is plugin-driven and may compute dynamic values.

The current hardcoded completion logic will be refactored toward the same
generic extension model so that built-in behavior and external plugins share
one completion architecture.

#### Behavior When Plugins Are Disabled or Removed

If persisted resources reference a plugin that is disabled or missing:

* read-oriented commands should continue to work where possible on raw config
* operational commands that require plugin factories or runtime logic must
  fail clearly
* the error must identify the missing or disabled plugin
* load failures should point operators to the plugin management commands that
  remain available through the plugin-safe bootstrap path

#### Compatibility

Plugin compatibility is versioned through a dedicated plugin API version.

For v1, the descriptor must declare:

* `plugin_api_version`

Support for additional Shepherd min/max version constraints can be added later
without changing the basic model.

#### Plugin Lifecycle Commands

Shepherd will expose core commands for plugin management:

* `shepctl plugin install <archive>`
* `shepctl plugin list`
* `shepctl plugin get <plugin-id>`
* `shepctl plugin enable <plugin-id>`
* `shepctl plugin disable <plugin-id>`
* `shepctl plugin remove <plugin-id>`

Install behavior:

* installing a new `id` creates a new managed plugin install
* reinstalling the same `id` and `version` is rejected unless explicitly
  forced
* installing the same `id` with a newer `version` is treated as an upgrade
* replacement of the managed plugin directory happens only after validation
  succeeds

### Consequences

* Good, because the CLI tree becomes structurally compatible with plugin
  extension.
* Good, because plugin ownership of templates and factories remains explicit.
* Good, because config is the durable registry of installed and disabled
  plugins.
* Good, because fail-fast startup avoids ambiguous partial behavior.
* Neutral, because core will not be fully migrated to a plugin immediately.
* Bad, because the work spans CLI, completion, config, factory, and install
  flows and must therefore be phased carefully.

### Confirmation

The implementation should be considered aligned with this ADR when:

* the CLI uses the `scope verb` shape consistently
* plugin inventory is persisted in the main config
* enabled plugins load at startup through descriptor validation and
  `importlib`
* command/factory/template/completion collisions are detected during startup
* plugin-owned templates and factories are addressable through canonical
  namespaced ids
* automated tests cover at least one fixture plugin end to end

## Pros and Cons of the Options

### Refactor CLI First, Then Build Plugins

* Good, because the plugin system targets the final command model.
* Good, because completion and collision rules can be designed once.
* Good, because it avoids building extension APIs against a CLI shape already
  considered temporary.
* Bad, because plugin work starts one phase later.

### Keep Current CLI and Build Plugins Around It

* Good, because it appears to reduce immediate scope.
* Bad, because direct command injection is harder to reason about.
* Bad, because later CLI refactors would leak into every plugin interface.
* Bad, because completion routing would likely need to be rewritten twice.

### Copy Plugin Templates Into Main Config

* Good, because it matches the current template storage model.
* Bad, because install, upgrade, disable, and removal become destructive
  config migrations.
* Bad, because template ownership becomes ambiguous over time.

### Keep Templates Plugin-Owned in Runtime Registries

* Good, because plugin lifecycle stays self-contained.
* Good, because namespaced ids make ownership and collisions explicit.
* Good, because uninstall and upgrade do not require copying templates back
  out of main config.
* Bad, because the config and lookup layers must be refactored.

## Rollout Plan

The work should be delivered in small, logically consistent PRs. Each PR
should land with focused commits and passing tests.

### PR 1: CLI Shape Refactor

Goal:

* move core commands from `verb scope` to `scope verb`

Scope:

* refactor `src/shepctl.py` command tree
* keep behavior unchanged apart from command paths
* update shell completion routing for the new command tree
* update docs and tests affected by the command rename

Suggested commits:

* `refactor(cli): move core commands to scope-verb layout`
* `test(cli): update command and completion coverage for scope-verb`
* `docs(cli): update examples to the new command tree`

### PR 2: Plugin Domain Model and Config Persistence

Goal:

* introduce the config model for plugins without runtime loading yet

Scope:

* add plugin config dataclasses and parsing/storage support
* add managed plugin root constants and directory handling
* add descriptor model and validation helpers
* add fixture data and unit tests for parsing and persistence

Suggested commits:

* `feat(config): persist installed plugins in main config`
* `feat(plugin): add descriptor schema and validation helpers`
* `test(config): cover plugin inventory parsing and storage`

### PR 3: Plugin Lifecycle Commands

Goal:

* add `plugin install/list/get/enable/disable/remove`

Scope:

* archive validation and extraction into the managed plugin root
* config mutation for install and state changes
* read-only inspection commands for installed plugins
* tests covering lifecycle and failure cases

Suggested commits:

* `feat(plugin): add install and remove commands`
* `feat(plugin): add list get enable disable commands`
* `test(plugin): cover lifecycle command flows`

### PR 4: Runtime Plugin Loader and Registries

Goal:

* load enabled plugins at startup and register their contributions

Scope:

* root plugin interface and typed contribution interfaces
* descriptor-driven `importlib` loading
* runtime registries for scopes, verbs, templates, completion, env factories,
  and svc factories
* fail-fast collision detection and startup errors
* one in-repo fixture plugin for integration-style tests

Suggested commits:

* `feat(plugin): add startup loader and registry bootstrap`
* `feat(plugin): register commands templates and factories`
* `test(plugin): add fixture plugin integration coverage`

### PR 5: Completion Extensibility

Goal:

* move completion onto the shared plugin extension model

Scope:

* introduce generic completion provider hooks
* adapt current core completion logic behind the same interfaces
* support dynamic plugin completion values
* extend tests for core and fixture-plugin completion

Suggested commits:

* `refactor(completion): add plugin-driven completion providers`
* `test(completion): cover dynamic plugin completion flows`

### PR 6: Factory and Template Refactor

Goal:

* remove hardcoded factory dispatch and move lookups to registries

Scope:

* adapt env/service managers to resolve namespaced factories
* adapt template lookup to unified runtime registries
* persist canonical template and factory ids
* tests for built-in and plugin-backed resources

Suggested commits:

* `refactor(factory): resolve env and svc factories via registries`
* `refactor(config): use canonical namespaced template identifiers`
* `test(factory): cover plugin-backed env and service resolution`

### PR 7: Core Contribution Alignment

Goal:

* align built-in behavior with the plugin architecture without requiring a
  full core-as-plugin migration yet

Scope:

* wrap core contributions through the same registry contracts where practical
* remove now-redundant static wiring from CLI/completion/factory paths
* document the remaining gap to a full built-in core plugin

Suggested commits:

* `refactor(core): align built-in contributions with plugin contracts`
* `docs(plugin): document current core alignment and next migration step`

## More Information

This ADR supersedes the earlier high-level proposal in
[0002-shepherd-plugin-design](./0002-shepherd-plugin-design.md) by fixing the
target CLI model, plugin ownership rules, and delivery plan.

The expected execution order is:

1. land the CLI refactor first
2. add plugin persistence and lifecycle
3. add runtime loading and registries
4. migrate completion and factory/template lookups
5. align built-in core contributions afterward
