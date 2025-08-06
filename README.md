# Shepherd

[![license](https://img.shields.io/badge/license-AGPL%20V3-blue)](https://github.com/MoonyFringers/shepherd/blob/master/LICENSE)
[![codecov](https://codecov.io/gh/MoonyFringers/shepherd/branch/main/graph/badge.svg)](https://codecov.io/gh/MoonyFringers/shepherd)

Shepherd functions as a specialized orchestration tool designed to streamline
the provisioning of development platforms.

> 📌 **Note:** Should a bug be found and not expected to be related with
> [known issues][issues], one should feel encouraged to file a new issue.

## Key Concepts

Shepherd utilizes two types of images:

1. **Docker Images**
2. **Environment Images**

### Docker Images

Classic stateless images containing executables.

### Environment Images

Environment images capture a snapshot of a specific reference platform
at a given point in time.
These images are more comprehensive, including:

- **Database State**: The complete state of the database is embedded within
  the environment image, allowing it to be immediately consumed by the
  corresponding database Docker image with no additional processing required.

- **Service Deployments**: The snapshot can also include the deployment state
  of services which are ready for immediate use upon consumption.

Once an environment image is pulled and imported into shepherd,
the corresponding environment state will evolve privately.

## Requirements

### OS & System Services

- **Linux**
  - Debian derived

## Installation

Set the `VER` environment variable to specify the desired version of the tool:

Use the `VER` env variable to specify the desired tool's version.

```bash
VER=0.0.0 sh -c "$(curl -sfL https://raw.githubusercontent.com/MoonyFringers/shepherd/main/scripts/install.sh)"
```

For advanced installation options and customization, refer to the
[installation guide][install].

## Consuming Environment Images

An environment image is typically created once, then pushed to the registry,
where it can be pulled and consumed countless times by any developer.
This ensures uniformity across different instances and reduces setup time.

Refer to documentation for [Consuming Environment Images].

## Authoring Environment Images

For creating, maintaining and pushing environment images to the registry refer
to [Authoring Environment Images].

## Full Commands and Options Documentation

Refer to the specific documentation for the currently supported commands
and options of [shepctl].

## Develop Shepherd

See our [development][development] documentation.

[issues]: https://github.com/MoonyFringers/shepherd/issues
[Consuming Environment Images]: docs/env-consume.md
[Authoring Environment Images]: docs/env-auth.md
[shepctl]: docs/shepctl.md
[development]: docs/development.md
[install]: docs/install.md
