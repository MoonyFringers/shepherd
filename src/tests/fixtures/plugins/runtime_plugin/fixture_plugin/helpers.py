"""
Fixture helper module imported through a package-absolute path.

The runtime loader tests keep this in a separate module to prove that plugin
packages can import their own siblings with statements like
`from fixture_plugin.helpers import ...`.
"""

COMPLETION_PROVIDER = "observability-completion"
