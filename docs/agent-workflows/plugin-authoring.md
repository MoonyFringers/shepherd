Plugin authoring
=================

Use this when building or modifying a shepherd plugin. `docs/plugins.md`
is the full spec (759 lines); this is the actionable step-by-step
companion — read `docs/plugins.md` for exact schema field lists, this
document for how to actually get a plugin installed and working.

Reference examples
--------------------

- `examples/plugins/hello-plugin/` — minimal reference exercising all
  four extension points (commands, completion, service factory, env
  factory). Copy its shape.
- `examples/plugins/fragment-demo/` — two cooperating plugins showing
  `env_template_fragments` and `depends_on`.

Layout
-------

```text
my-plugin/
  plugin.yaml
  my_plugin/
    __init__.py
    main.py         # ShepherdPlugin subclass, wires everything below
    commands.py      # click.Command per verb
    completion.py     # completion provider functions
    factories.py       # env/svc factory classes
  README.md
```

`plugin.yaml` essentials
--------------------------

Required: `id`, `name`, `version`, `plugin_api_version` (currently `1`),
`entrypoint.module`, `entrypoint.class`. Optional: `description`,
`capabilities` (booleans: `templates`, `commands`, `completion`,
`env_factories`, `svc_factories`, `remote_backends` — must be real YAML
booleans, not strings), `default_config`, `depends_on`,
`env_template_fragments`, `env_templates`, `service_templates`.

Declared `capabilities` must match what the plugin class's getters
actually return, or validation fails at load time.

Entrypoint class
------------------

Subclass `ShepherdPlugin`, override the getters for whatever
capabilities you declared:

```python
class MyPlugin(ShepherdPlugin):
    def get_commands(self) -> Sequence[PluginCommandSpec]: ...
    def get_completion_providers(self) -> Sequence[PluginCompletionSpec]: ...
    def get_env_factories(self) -> Sequence[PluginEnvFactorySpec]: ...
    def get_service_factories(self) -> Sequence[PluginSvcFactorySpec]: ...
```

`self.context: PluginContext` is available in every getter and in any
command closures built from `get_commands()`. It exposes `.config`
(read-only query of environments/templates/plugin config),
`.environment`/`.service`/`.remote` (lifecycle operations, `None` only
during tab-completion resolution).

Commands that need `self.context` must be built as closures — a
free-standing `click.Command` (like hello-plugin's simple `greet`) has
no access to it. Pattern:

```python
def make_my_command(context: PluginContext) -> click.Command:
    @click.command(name="my-verb")
    def my_command() -> None:
        ...  # use context here
    return my_command
```

then in `get_commands()`:

```python
return [PluginCommandSpec(scope="my-plugin", verb="my-verb",
                          command=make_my_command(self.context))]
```

Env/service factories
------------------------

If the target stack is docker-compose based (the common case), don't
write custom `Environment`/`Service` subclasses — delegate to the
built-in `DockerComposeEnv`/`DockerComposeSvc`, exactly like
hello-plugin's `factories.py` does:

```python
class MyServiceFactory(ServiceFactory):
    @classmethod
    def get_name_impl(cls) -> str:
        return "my-plugin-svc"

    def new_service_from_cfg_impl(self, envCfg, svcCfg, cli_flags=None):
        return DockerComposeSvc(self.config, envCfg, svcCfg, cli_flags=cli_flags)


class MyEnvironmentFactory(EnvironmentFactory):
    def __init__(self, configMng, svcFactory, cli_flags=None):
        self.configMng = configMng
        self.svcFactory = svcFactory
        self.cli_flags = cli_flags or {}

    def new_environment_impl(self, env_tmpl_cfg, env_tag):
        return DockerComposeEnv(
            self.configMng, self.svcFactory,
            self.configMng.env_cfg_from_tag(env_tmpl_cfg, env_tag),
            cli_flags=self.cli_flags,
        )
```

`ContainerCfg` supports a `healthcheck` field, mirroring compose's
native `healthcheck:` block directly (`test`/`interval`/`timeout`/
`retries`/`start_period`) — it's rendered straight into the generated
compose YAML and polled by Docker itself, distinct from `ProbeCfg`
(a disposable one-shot service run via `compose run --rm`):

```yaml
containers:
  - image: postgres:16-alpine
    tag: app
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myuser"]
      interval: "5s"
      timeout: "3s"
      retries: 5
```

For a docker-compose `profiles:`-equivalent — an optional, opt-in
service within an environment template — mark the service_templates
ref `optional: true`. `env add` excludes it by default; bring it in
explicitly afterwards against the checked-out environment:

```yaml
env_templates:
  - tag: full
    service_templates:
      - template: app
        tag: app
      - template: crawler
        tag: crawler
        optional: true   # excluded by `env add`, not part of the base env
```

```sh
shepctl env add my-plugin/full my-env
shepctl env checkout my-env
shepctl svc add my-plugin/crawler crawler   # opt in explicitly
shepctl env up                              # now starts crawler too
```

Install / enable / test loop
-------------------------------

`plugin install` requires a **tar archive**, not a bare directory —
despite what hello-plugin's own README currently says
([MoonyFringers/shepherd#262](https://github.com/MoonyFringers/shepherd/issues/262)).
Build one explicitly listing contents, **not** `tar czf x.tar.gz .` —
a `.` top-level entry is rejected by the extraction path check
([MoonyFringers/shepherd#263](https://github.com/MoonyFringers/shepherd/issues/263)):

```sh
cd my-plugin
tar czf /tmp/my-plugin.tar.gz plugin.yaml my_plugin README.md
```

Then:

```sh
python3 src/shepctl.py plugin install /tmp/my-plugin.tar.gz --force
python3 src/shepctl.py plugin enable my-plugin
python3 src/shepctl.py plugin get my-plugin   # confirm descriptor validated
```

There is no `env template list` / `svc template list` command
([MoonyFringers/shepherd#264](https://github.com/MoonyFringers/shepherd/issues/264)).
Validate templates registered by adding an environment from one
directly:

```sh
python3 src/shepctl.py env add my-plugin/<template-tag> <env-tag>
python3 src/shepctl.py env checkout <env-tag>
python3 src/shepctl.py env up      # no positional tag; uses checked-out env
python3 src/shepctl.py env halt
python3 src/shepctl.py env delete <env-tag>
```

`env up`/`env halt` take no positional tag despite `env add`'s
two-positional-arg form
([MoonyFringers/shepherd#265](https://github.com/MoonyFringers/shepherd/issues/265))
— check out the env first.

Lifecycle commands
---------------------

```sh
shepctl plugin list
shepctl plugin get <plugin-id>
shepctl plugin install <archive> [--force]
shepctl plugin enable <plugin-id>
shepctl plugin disable <plugin-id>
shepctl plugin remove <plugin-id>
```

Filing gaps
------------

Building a real plugin against a real stack routinely surfaces gaps in
this API (the six above were all found and filed the same way). File
them as issues on `MoonyFringers/shepherd`, don't just work around them
silently — this project's plugin system has so far only been exercised
by toy examples, and gap reports are how it gets better.

See also
--------

`docs/plugins.md` for the full descriptor schema, plugin inventory
config format, and `env_template_fragments`/`depends_on` details not
repeated here.
