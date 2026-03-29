"""Completion provider for the Hello Plugin.

A completion provider is a callable with the signature:

    f(args: list[str]) -> list[str]

It receives the full raw argument list and returns matching suggestions.
Shepherd calls all providers registered for the active scope and merges
their results.

Alternatively, implement the ``CompletionProvider`` protocol from
``plugin`` and pass the bound method as the provider:

    PluginCompletionSpec(scope="myscope", provider=obj.get_completions)
"""


def complete_hello(args: list[str]) -> list[str]:
    """Return completions for the ``hello`` scope."""
    if args[:2] == ["hello", "greet"]:
        # Suggest a few well-known names when the user is completing NAME.
        return ["world", "shepherd", "alice", "bob"]
    return []
