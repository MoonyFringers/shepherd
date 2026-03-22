"""
Fixture helper module imported through a package-absolute path.

The runtime loader tests keep this in a separate module to prove that plugin
packages can import their own siblings with statements like
`from fixture_plugin.helpers import ...`.

The helper also exposes the dynamic completion callable used by the plugin
fixture. That lets the tests cover both the import fix and the later runtime
execution path for plugin-provided completion values.
"""


def complete_observability(args: list[str]) -> list[str]:
    """Return dynamic completion values for the fixture plugin scopes."""
    if args[:2] == ["observability", "tail"]:
        return ["logs", "metrics", "traces"]
    if args[:2] == ["env", "doctor"]:
        return ["containers", "network", "volumes"]
    return []
