# Shepherd

[![license](https://img.shields.io/badge/license-AGPL%20V3-blue)](https://github.com/MoonyFringers/shepherd/blob/master/LICENSE)
[![codecov](https://codecov.io/gh/MoonyFringers/shepherd/branch/main/graph/badge.svg)](https://codecov.io/gh/MoonyFringers/shepherd)

Shepherd is a specialized orchestration platform designed to streamline
the provisioning of reproducible development platforms.

It helps define, start, inspect, and manage structured development
environments with `shepctl`, while providing a flexible foundation that
can be extended to support new workflows, platforms, and operational
patterns.

> 📌 **Note:** Should a bug be found and not expected to be related with
> [known issues][issues], one
> should feel encouraged to file a new issue.

## Extensibility

Shepherd is built as an **extensible platform**, not a fixed tool.

Core capabilities can be expanded through plugins that integrate
directly into the runtime and CLI, allowing teams to tailor Shepherd to
their infrastructure, workflows, and domain-specific needs.

Plugins can:

- Add new CLI scopes and commands
- Provide dynamic command completions
- Contribute reusable environment templates
- Define custom service and environment factories
- Extend provisioning logic without modifying core code

This design allows Shepherd to evolve alongside the systems it manages,
supporting organization-specific conventions while keeping the core
runtime stable and predictable.

See the [plugin documentation](docs/plugins.md) for details on how
plugins integrate with Shepherd.

## Getting Started

Install `shepctl`:

```bash
VER=<release-tag> sh -c "$(curl -sfL https://raw.githubusercontent.com/MoonyFringers/shepherd/main/scripts/install.sh)"
```

Then:

1. Pick a sample configuration from [`examples/configurations`](examples/configurations).
2. Pick a sample plugin from [`examples/plugins`](examples/plugins).
3. Review the available commands with `shepctl --help`.
4. Read the [installation guide](docs/install.md) for setup details and
    advanced options.

## Key Concepts

Shepherd works with two image concepts:

1. **Docker Images**
2. **Environment Images**

### Docker Images

Regular stateless container images that run application or utility code.

### Environment Images

Environment images capture a reusable snapshot of a reference platform
at a specific point in time.

Once an environment image is pulled and imported into Shepherd, that
local environment evolves independently for each developer.

## Requirements

### OS & System Services

- **Linux**
  - Debian derived

## Documentation

- [Installation guide][install]
- [Consuming Environment Images][Consuming Environment Images]
- [Authoring Environment Images][Authoring Environment Images]
- [shepctl command reference][shepctl]
- [Development guide][development]

## Develop Shepherd

See our [development][development] documentation.

[issues]: https://github.com/MoonyFringers/shepherd/issues
[Consuming Environment Images]: docs/env-consume.md
[Authoring Environment Images]: docs/env-auth.md
[shepctl]: docs/shepctl.md
[development]: docs/development.md
[install]: docs/install.md
