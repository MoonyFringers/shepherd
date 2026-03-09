# shepctl

`shepctl` is the Shepherd command-line interface for managing
environments, services, and probes.

## Global Options

These options apply to every command:

- `-v`, `--verbose`: enable verbose mode
- `--quiet`: suppress command output
- `-y`, `--yes`: answer yes to prompts automatically

## Command Overview

Top-level commands currently available:

- `add`
- `build`
- `check`
- `checkout`
- `clone`
- `delete`
- `get`
- `halt`
- `list`
- `logs`
- `reload`
- `rename`
- `shell`
- `status`
- `up`

## Commands

### `get`

Read configuration data without changing runtime state.

#### `get env [TAG]`

Get environment configuration.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `--by-gate`: group target configuration by gate, requires `--target`
- `-r`, `--resolved`: return resolved configuration

#### `get probe [PROBE_TAG]`

Get probe configuration for the active environment.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `-r`, `--resolved`: return resolved configuration
- `-a`, `--all`: return all probes

Requires an active environment.

#### `get svc TAG`

Get service configuration for the active environment.

Options:

- `-o`, `--output [yaml|json]`: output format
- `-t`, `--target`: return target configuration
- `-r`, `--resolved`: return resolved configuration

Requires an active environment.

### `add`

Create resources.

#### `add env TEMPLATE TAG`

Create a new environment from an environment template.

#### `add svc SVC_TEMPLATE SVC_TAG [SVC_CLASS]`

Add a service to the active environment.

Requires an active environment.

### `clone`

#### `clone env SRC_TAG DST_TAG`

Clone an environment.

### `rename`

#### `rename env SRC_TAG DST_TAG`

Rename an environment.

### `checkout TAG`

Set the active environment.

### `delete`

#### `delete env TAG`

Delete an environment.

### `list`

List environments.

### `up`

Start resources.

When used without a subcommand, `up` behaves like `up env` for the active
environment.

Shared environment options:

- `--details`: show extra details in status tables
- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `--timeout INTEGER`: max seconds to wait for containers to be running
- `-w`, `--watch`: keep updating output until interrupted

#### `up env`

Start the active environment explicitly.

Requires an active environment.

#### `up svc SVC_TAG [CNT_TAG]`

Start a service, optionally targeting one container.

Requires an active environment.

### `halt`

Stop resources.

When used without a subcommand, `halt` behaves like `halt env` for the
active environment.

Shared environment options:

- `--no-wait`: return immediately after sending the stop command

#### `halt env`

Stop the active environment explicitly.

Requires an active environment.

#### `halt svc SVC_TAG [CNT_TAG]`

Stop a service, optionally targeting one container.

Requires an active environment.

### `reload`

Reload resources.

#### `reload env`

Reload the active environment.

Options:

- `--details`: show extra details in status tables
- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `-w`, `--watch`: keep updating output until interrupted

Requires an active environment.

#### `reload svc SVC_TAG [CNT_TAG]`

Reload a service, optionally targeting one container.

Requires an active environment.

### `build SVC_TAG [CNT_TAG]`

Build a service, optionally targeting one container.

Requires an active environment.

### `logs SVC_TAG [CNT_TAG]`

Show service logs, optionally for a specific container.

Requires an active environment.

### `shell SVC_TAG [CNT_TAG]`

Open a shell for a service, optionally for a specific container.

Requires an active environment.

### `status`

Show resource status.

When used without a subcommand, `status` behaves like `status env` for the
active environment.

Shared environment options:

- `--details`: show extra details in status tables
- `--show-commands`: show recent command history in status panels
- `--show-commands-limit INTEGER`: number of commands to display
- `-w`, `--watch`: keep updating output until interrupted

#### `status env`

Show status for the active environment explicitly.

Requires an active environment.

### `check`

Run validation commands.

#### `check probe [PROBE_TAG]`

Run probes for the active environment and exit with a probe-based status
code.

Options:

- `-a`, `--all`: run all probes

Requires an active environment.

## Notes

- Many commands operate on the active environment selected with `checkout`.
- Commands that manage environment runtime state are centered around
  `up`, `halt`, `reload`, and `status`.
- Service-oriented commands (`build`, `logs`, `shell`, `up svc`,
  `halt svc`, `reload svc`) all target the active environment.
