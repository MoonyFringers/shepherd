# shepctl

## Database Service

```sh
shepctl db build
```

Build the database management system (DBMS) image.

```sh
shepctl db bootstrap
```

Bootstrap the database management system (DBMS) service.

---

```sh
shepctl db up
```

Start the DBMS service.

---

```sh
shepctl db halt
```

Stop the DBMS service.

---

```sh
shepctl db reload
```

Reload the DBMS service.

---

```sh
shepctl db stdout
```

Show DBMS service stdout.

---

```sh
shepctl db shell
```

Open a shell session within the DBMS service container.

---

```sh
shepctl db sql-shell
```

Open a `sql-shell` session for the DBMS service.

---

```sh
shepctl db create user [user] [psw]
```

Create a new user in the database with the specified username and password.

---

```sh
shepctl db create dir [user] [directory-name]
```

Create a new directory object in the database for the specified user.

---

```sh
shepctl db drop user [user]
```

Delete an existing user from the database.

---

> **NOTE** This parameter setting is valid only for Oracle.

```sh
shepctl db import dump [user] [dump-file] [schema]
                    [dump-file] [schema]
                    [import-config-file]
```

Import an existing schema into the database from a dump file or import
configuration file.

---

> **NOTE** This parameter setting is valid only for PostgreSQL.

```sh
shepctl db import dump [dump-file]
```

Import a dump in the database.

---

```sh
shepctl db exec script [sql-file]
                    [sql-file] [user] [pwd]
```

Execute a `sql` script as a sys user or a specified user with password.

---

```sh
shepctl db list users
```

List all users in the DBMS.

---

```sh
shepctl db upstream [remote]
```

Use an upstream DBMS.

---

```sh
shepctl db downstream
```

Set DBMS to the local (downstream) service

---

```sh
shepctl db sync [upstream]
```

Sync the DBMS local service's status with an upstream DBMS.

## Environment Management

```sh
shepctl env init [db-type] [env-tag]
```

Initialize a new environment with a specified DBMS type and environment tag name.

---

```sh
shepctl env clone [src-env-tag] [dst-env-tag]
```

Clone an existing environment (requires root privileges).

---

```sh
shepctl env checkout [env-tag]
```

Checkout an environment.

---

```sh
shepctl env noactive
```

Set all environments as non-active.

---

```sh
shepctl env list
```

List all available environments.

---

```sh
shepctl env up
```

Start the environment.

---

```sh
shepctl env halt
```

Stop the environment.

---

```sh
shepctl env reload
```

Reload the environment.

---

```sh
shepctl env status
```

Display the status of the specified environment.

---

```sh
shepctl env clean
```

Clean up the specified environment.

---

```sh
shepctl env archive [env-tag]
```

Archive the specified environment (requires root privileges).

---

```sh
shepctl env restore [env-tag]
```

Restore an archived environment (requires root privileges).

---

```sh
shepctl env push [env-tag]
```

Push an environment image to the environment registry.

---

```sh
shepctl env fetch [env-tag]
```

Fetch an environment image from the environment registry.

---

```sh
shepctl env pull [env-tag]
```

Fetch an environment image from the environment registry and import it.

## Environment Registry

```sh
shepctl reg list
```

List all the environment images on the environment registry.

## System

```sh
shepctl [--all] sys prune
```

Delete all the archived environments and their archived images.

## Available Env-Vars

### SHPD_CFG_PATH

Specify shepctl's config file (default: ~/.shepctl.json).

### SHPD_DB_CONTAINER_NAME

Specify the dbms docker container name.

### SHPD_ENVS_BASE_DIR

Specify the base directory to use for storing the environments.

### SHPD_ENV_TAG

Specify the environment's tag to use.

### SHPD_ENV_DB_TYPE

Specify the environment's dbms to use: Oracle or Postgres.

### SHPD_ENV_DB_DATA_REL_DIR

Specify the relative directory used by dbms to store its data.

### SHPD_ENV_DB_SHARED_REL_DIR

Specify the relative directory used by dbms to mount its directory objects.

### SHPD_DB_REGISTRY

Specify the dbms docker upstream registry.

### SHPD_DB_TAG

Specify the dbms docker image tag.

### SHPD_ENV_DB_SYS_USER

Specify the dbms sys user to use.

### SHPD_ENV_DB_SYS_PSW

Specify the dbms sys password to use.

### SHPD_ENV_DB_APP_USER

Specify the dbms user to use for the environment.

### SHPD_ENV_DB_APP_PSW

Specify the dbms user password to use for the environment.

### SHPD_ENV_ORA_PUMP_DIR_NAME

Specify the Oracle's pump directory name.

### SHPD_ENV_ORA_ROOT_DB_NAME

Specify the Oracle's container database (CDB) name.

### SHPD_ENV_DB_NAME

Specify the database name.

### SHPD_ENV_DB_NET_LST_PORT_HOST

1. Specify the Oracle-host port mapping for the Oracle Net
Listener Port (1521).
2. Specify the Postgres-host port mapping for the Postgres Net
Listener Port (5432).
