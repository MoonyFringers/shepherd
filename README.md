# Shepherd

[![license](https://img.shields.io/badge/license-AGPL%20V3-blue)](https://github.com/MoonyFringers/shepherd/blob/master/LICENSE)
[![codecov](https://codecov.io/gh/MoonyFringers/shepherd/branch/main/graph/badge.svg)](https://codecov.io/gh/MoonyFringers/shepherd)

Shepherd functions as a specialized orchestration tool designed to streamline
the provisioning of development platforms.

It helps define, start, inspect, and manage reproducible development
environments with `shepctl`.

> 📌 **Note:** Should a bug be found and not expected to be related with
> [known issues][issues], one should feel encouraged to file a new issue.

## Getting Started

Install `shepctl`:

```bash
VER=<release-tag> sh -c "$(curl -sfL https://raw.githubusercontent.com/MoonyFringers/shepherd/main/scripts/install.sh)"
```

Then:

1. Pick a sample configuration from [`examples/`](examples/README.md).
2. Review the available commands with `shepctl --help`.
3. Read the [installation guide][install] for setup details and advanced options.

## Key Concepts

Shepherd works with two image concepts:

1. **Docker Images**
2. **Environment Images**

### Docker Images

Regular stateless container images that run application or utility code.

### Environment Images

Environment images capture a reusable snapshot of a reference platform at
a specific point in time. They can include:

- **Database state**: a preloaded database that can be consumed immediately.
- **Service state**: service deployments that are already prepared for use.

Once an environment image is pulled and imported into Shepherd, that local
environment evolves independently for each developer.

## Requirements

### OS & System Services

- **Linux**
  - Debian derived

## Examples

Sample `shpd.yaml` configurations are available in [`examples/`](examples/README.md):

- [`examples/minimal/`](examples/minimal/README.md)
- [`examples/env-basic/`](examples/env-basic/README.md)
- [`examples/env-with-probes/`](examples/env-with-probes/README.md)
- [`examples/svc-basic/`](examples/svc-basic/README.md)

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
