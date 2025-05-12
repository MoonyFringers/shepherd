# Consuming Environments

After installing `shepctl` on your system, a directory named
`.hdenvs` will be created in your home directory.
This is where the tool manages and stores all your environments.
Each environment is isolated within its own private directory,
ensuring smooth management of multiple environments.

The directory structure is organized as follows:

hdclt

```text
.hdenvs/
  my-env-1/
    db/
      shared/
      data/
        ...
    svc-1/
      primary/
        local/
        server/
        shared/
  ...
  .certs
  .env_images
  .ssh
  .sshd
...
```

## Understanding the Directory Structure

- **Environment Directories**: Each environment has its own
  dedicated root directory, named after the environment itself
  (e.g., `my-env-1`).

- **Database (`db`) Directory**: Inside the environment directory,
  the `db` folder contains subdirectories such as `shared` and `data`,
  which store database-specific files.
  These directories are mounted to the respective database Docker
  service.

- **SVC (`svc`) Directory**: The `svc` directory holds configuration
  and data for the service(s), with subdirectories like `local`, `server`,
  and `shared`. These subdirectories are mounted to the SVC Docker service.

### System-Level Directories

- **`.env_images`**: This directory contains archived (tar.gz) images that
  have been pulled from the environment registry.
  These images represent snapshots of environments.

- **`.certs`**: This directory contains certificates used by an ingress service
  such as Traefik or Nginx.

- **`.ssh`**: This directory contains the `authorized_keys` for the host.
  This ensures consistent SSH configurations across environments,
  making it easier to manage access.

- **`.sshd`**: The `.sshd` directory holds the SSH daemon configuration,
  which is shared by all services.

## Listing Local Environments

To view a list of all the environments currently available on your
local machine, use the following command:

```bash
$ shepctl env list
Environment  Flags
-----------  -----

Environments   0
Live Size      0  (G)
Archived Size  0  (G)
Total Size     0  (G)
```

This output is expected when **`shepctl`** has been freshly installed.
As you create, import, or clone environments, this list will populate
with details about the environments you're managing.

### Understanding Flags

The `Flags` column in the output can assume the following:

- **active**: An active environment can be started,
  meaning you can work with it, run services, and perform all
  environment-related operations. It is set up and ready for consumption.

- **archived**: An archived environment only retains its image
  in the form of a `tar.gz` file. The environment itself is not set
  up or ready to be consumed. Archiving an environment is a useful
  space-saving option, especially for environments that are not
  frequently used.
  When needed, the environment can be restored from the archive.

## Listing Remote Environments

If the environment you want to use is not already available locally,
you can check if it exists in the repository.
To do so, use the following command:

```bash
$ shepctl reg list
Environment      Size
-----------      ----
...
head-MyAbiGVL      466.45  (M)
head-PelixSNDE     5.06    (G)
...
```

### Pulling Environments

Once you've identified the environment you wish to use,
you can pull and import it into your local setup by running:

```bash
$ shepctl --checkout env pull head-MyAbiGVL
...
head-MyAbiGVL imported.
head-MyAbiGVL active.
```

## Managing Environments: Selecting, Starting, Stopping, and Restarting

### Selecting an Environment

To select an environment to work with:

```shell
$ shepctl env checkout head-MyAbiGVL
Switched to head-MyAbiGVL.
```

### Starting an Environment

To start the selected environment:

```shell
shepctl env up
```

### Stopping an Environment

To stop the selected environment:

```shell
shepctl env halt
```

### Restarting an Environment

To restart the environment (stop and start):

```shell
shepctl env reload
```
