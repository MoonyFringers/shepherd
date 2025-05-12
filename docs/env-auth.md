# Authoring Environments

Creating and maintaining images for **development** platforms is a
critical process, particularly when the images are designed to be immediately
consumable by developers.

This approach streamlines the development workflow by ensuring that
environments are standardized, consistent, and readily available for
deployment.

## Core Principles

### Single Creation, Multiple Consumption

An environment is typically created once, then pushed to the registry,
where it can be pulled and consumed countless times by any developer.

### Specialized Support for Database Services

**shepherd** offers enhanced support in:

- **State Management**: The environment's creator or maintainer can easily
  manipulate the state of the database, enabling them to tailor the
  environment to specific development needs.

- **Database Import**: Importing database dumps is straightforward,
  allowing for quick replication of data within the development environment.

## Creating a New Environment

Creating a new environment can be approached using various strategies,
depending on your specific requirements.

### Starting from Scratch

If you need a clean slate, you can initialize an entirely new,
empty environment. This approach allows you to define the database type
(`ora` for Oracle, `pg` for PostgreSQL) right from the outset.
To do this, simply execute the following command:

```bash
$ shepctl --checkout env init ora my-new-env
my-new-env [ora].
my-new-env active.
```

This command creates a new environment named `my-new-env`
configured with the specified database type.

#### Starting the Database Service

Once the environment is active, you'll likely want to start the database service:

```bash
$ shepctl db up
Oracle database must be created for environment: my-new-env, this can take long...
[+] Running 1/1
 ✔ Container db-my-new-env  Started 0.3s
Oracle Database is not ready yet. - Timeout in 1189 seconds
```

Since the environment is a fresh instance, the database service needs to
initialize and build its structure on the disk from scratch.
This process may take some time.

To monitor the progress of this initialization, you can follow the
standard output of the database service in real-time from another shell:

```bash
$ shepctl -f db stdout
[2024:09:03 15:25:15]: Acquiring lock .ORCLCDB.create_lck with heartbeat 30 secs
[2024:09:03 15:25:15]: Lock acquired
[2024:09:03 15:25:15]: Starting heartbeat
[2024:09:03 15:25:15]: Lock held .ORCLCDB.create_lck
ORACLE EDITION: ENTERPRISE
...
Prepare for db operation
8% complete
Copying database files
31% complete
Creating and starting Oracle instance
32% complete
...
#########################
DATABASE IS READY TO USE!
#########################
...
```

Now, you can import a database's dump into the environment.

### Using a Fresh Database Environment Image

To save time during the initial database setup, you can opt to use
a pre-built, fresh database environment image.
This approach bypasses the lengthy initialization phase,
allowing you to start working with a fully configured database
almost immediately.

#### Querying Available Fresh Database Images

To view the available pre-built environment images in the repository,
you can run the following command:

```bash
$ shepctl reg list
Environment      Size
-----------      ----
fresh-ora-19300  632.98  (M)
...
```

By convention, clean environment images are typically prefixed
with `fresh-`, indicating that they are clean and pre-initialized.
Selecting one of these images allows you to skip the initial database
setup.

To pull the image and import the environment run:

```bash
$ shepctl --checkout env pull fresh-ora-19300
...
fresh-ora-19300 imported.
fresh-ora-19300 active.
```

Now, you'll likely want to start the database service:

```bash
$ shepctl db up
[+] Running 1/1
 ✔ Container db-fresh-ora-19300  Started 0.3s
Oracle Database is ready.
```

Now, you can import a database's dump into the environment.

### Cloning an Existing Environment Image

A common use case is when you need to upgrade an existing environment
to a new branch version or make specific modifications while preserving
the original environment. Cloning allows you to create an independent copy,
so you can work freely without affecting the source environment.

#### Querying Available Environment Images

If the environment you want to clone is not already available locally,
you can first check if it exists in the repository.
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

Once you've identified the environment you wish to clone,
you can pull and import it into your local setup by running:

```bash
$ shepctl --checkout env pull head-MyAbiGVL
...
head-MyAbiGVL imported.
head-MyAbiGVL active.
```

#### Cloning the Environment

With the environment imported, you can proceed to clone
it to a new environment. This process creates a copy of the original,
which you can modify as needed:

```bash
$ shepctl --checkout env clone head-MyAbiGVL branch-MyAbiGVL-202501
...
head-MyAbiGVL cloned to branch-MyAbiGVL-202501.
branch-MyAbiGVL-202501 active.
```

Now, you can proceed with making any necessary modifications to the
cloned environment without impacting the original one,
ensuring that both environments remain intact and available for
different purposes.

### Importing a Database Dump into the Environment

To import a database dump into the environment you must first move the
dump file into the `db/shared` directory of the environment:

```text
.hdenvs/
  my-env/
    db/
      shared/
        src-db.dmp
...
```

Once the dump file is prepared, you can use the following import command:

> **Note:** For Oracle databases, you must specify the schema name.

```bash
shepctl db import dump src-db.dmp my-schema
```

If the environment uses PostgreSQL, only the dump file name is required:

```bash
shepctl db import dump d_db.gz
```

### Publishing an Environment to the Registry

After finalizing and testing your newly crafted environment,
you can publish it to the registry to make it accessible to
other developers:

- Ensure the following directory is empty:

```text
.hdenvs/
  my-env/
    db/
      shared/
```

- Perform a clean with:

```shell
$ shepctl env clean
my-env cleaned.
```

- Make a snapshot of the environment:

```shell
$ shepctl --keep env archive
my-env is archiving, this can take long...
my-env archived.
```

- Push the snapshot to the registry:

```shell
shepctl env push my-env
```
