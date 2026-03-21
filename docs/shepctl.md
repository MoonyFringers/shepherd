# shepctl

`shepctl` is the Shepherd command-line interface for managing
environments, services, and probes.

## Global Options

These options apply to every command:

- `-v`, `--verbose`: enable verbose mode
- `--quiet`: suppress command output
- `-y`, `--yes`: answer yes to prompts automatically

## Command Overview

Top-level scopes currently available:

- `env`
- `probe`
- `svc`

## Commands

### `env`

Manage environments.

#### `env get [TAG]`

Get environment configuration.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `--by-gate`: group target configuration by gate, requires `--target`
- `-r`, `--resolved`: return resolved configuration

#### `env add TEMPLATE TAG`

Create a new environment from an environment template.

#### `env clone SRC_TAG DST_TAG`

Clone an environment.

#### `env rename SRC_TAG DST_TAG`

Rename an environment.

#### `env checkout TAG`

Set the active environment.

#### `env delete TAG`

Delete an environment.

#### `env list`

List environments.

#### `env up`

Start the active environment.

Shared environment options:

- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `--timeout INTEGER`: max seconds to wait for containers to be running
- `-w`, `--watch`: keep updating output until interrupted

Requires an active environment.

#### `env halt`

Stop the active environment.

Options:

- `--no-wait`: return immediately after sending the stop command

Requires an active environment.

#### `env reload`

Reload the active environment.

Options:

- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `-w`, `--watch`: keep updating output until interrupted

Requires an active environment.

#### `env status`

Show status for the active environment.

Options:

- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `-w`, `--watch`: keep updating output until interrupted

Requires an active environment.

### `probe`

Manage probes.

#### `probe get [PROBE_TAG]`

Get probe configuration for the active environment.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `-r`, `--resolved`: return resolved configuration
- `-a`, `--all`: return all probes

Requires an active environment.

#### `probe check [PROBE_TAG]`

Run probes for the active environment and exit with a probe-based status
code.

Options:

- `-a`, `--all`: run all probes

Requires an active environment.

### `svc`

Manage services.

#### `svc get TAG`

Get service configuration for the active environment.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `-r`, `--resolved`: return resolved configuration

Requires an active environment.

#### `svc add SVC_TEMPLATE SVC_TAG [SVC_CLASS]`

Add a service to the active environment.

Requires an active environment.

#### `svc up SVC_TAG [CNT_TAG]`

Start a service, optionally targeting one container.

Requires an active environment.

#### `svc halt SVC_TAG [CNT_TAG]`

Stop a service, optionally targeting one container.

Requires an active environment.

#### `svc reload SVC_TAG [CNT_TAG]`

Reload a service, optionally targeting one container.

Requires an active environment.

#### `svc build SVC_TAG [CNT_TAG]`

Build a service, optionally targeting one container.

Requires an active environment.

#### `svc logs SVC_TAG [CNT_TAG]`

Show service logs, optionally for a specific container.

Requires an active environment.

#### `svc shell SVC_TAG [CNT_TAG]`

Open a shell for a service, optionally for a specific container.

Requires an active environment.

## Notes

- Many commands operate on the active environment selected with `env checkout`.
- Commands that manage environment runtime state are centered around
  `env up`, `env halt`, `env reload`, and `env status`.
- Service-oriented commands (`svc build`, `svc logs`, `svc shell`,
  `svc up`, `svc halt`, `svc reload`) all target the active environment.
