---
status: "proposed"
date: 2025-09-09
decision-makers:
  - '@luca-c-xcv'
  - '@feed3r'
  - '@giubacc'
---

# Shepherd Plugin Design

## Context and Problem Statement

Shepherd is a container orchestration engine that manages environments
and services via templates.

Currently, all service definitions and customizations must be done
manually in templates.

We need to define what a *plugin* is in Shepherd, what responsibilities
it should have, and how it should integrate with the
[Shepherd Core Stack][shepherd-core-stack].

The main question is: **what functionality should a plugin provide,
and how should Shepherd load, distribute, and manage plugins?**

## Decision Drivers

* Need for modularity and reusability of service definitions
  (e.g., PostgreSQL, Oracle, proprietary services).
* Desire to allow companies and users to develop their own custom plugins.
* Avoiding bloat in the Shepherd core (core should not ship with plugins).
* Supporting both public and private plugins
  (different trust/security models).
* Enabling extensibility for CLI and service-specific interactions.
* Providing a way to share plugins through repositories but also allowing
  local-only development.

## Considered Options

* **Option A: Plugins as extensions for the core, offering:
  templates + CLI commands + provisioning logic**
* **Option B: No plugins, only manual templates**

## Decision Outcome

Chosen option: **Option A: Plugins as extensions for the core**.
A Shepherd plugin is defined as a Python object that:

1. Provides templates for services and environments.
2. Can reference and depend on other plugins
   (e.g., a proprietary plugin depending on the base PostgreSQL plugin).
3. Can define provisioning logic for services (e.g., initializing a database).
4. Can extend the Shepherd CLI with additional commands and completions
   (e.g., `shepctl my-service logs`).
5. Can be distributed via repositories (public or private) or installed
   locally.

### Consequences

* **Good**: Clear separation between core and extensions.
  Core remains minimal and agnostic.
* **Good**: Plugins can be reused across environments and projects.
* **Good**: Developers can build and distribute their own plugins
  without modifying Shepherd core.
* **Good**: Repository mechanism allows community-driven ecosystem
  of plugins.
* **Neutral**: Requires careful API design for plugins.
* **Bad**: Adds complexity to Shepherd
  (plugin loader, dependency resolution, repository management).

### Confirmation

* Shepherd must provide an abstract base class or interface for plugins.
* Unit/integration tests will verify that a plugin can:
  * Provide service/environment templates.
  * Extend CLI with additional commands.
  * Be loaded from both repository and local filesystem.

## Pros and Cons of the Options

### Option A: Plugins as extensions for the core

* Good, because it supports both templates and runtime features.
* Good, because it can extend CLI and provisioning logic.
* Good, because it allows composition of plugins.
* Bad, because it increases implementation complexity.
* Bad, because dependency and compatibility management may be tricky.

### Option B: No plugins, only manual templates

* Good, because it keeps Shepherd simple.
* Bad, because it reduces usability and reusability.
* Bad, because it prevents community ecosystem development.

## More Information

* Plugin loading will rely on Python’s dynamic import system.
* Shepherd will maintain a registry of configured plugin repositories.
* Plugins may be published in a public community repository
  or developed privately in local paths.

[shepherd-core-stack]: (https://github.com/MoonyFringers/shepherd)
