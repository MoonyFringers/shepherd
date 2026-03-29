"""CLI command contributions for the Hello Plugin."""

import click


@click.command(name="greet")
@click.argument("name", required=False)
def greet(name: str | None) -> None:
    """Print a greeting.  NAME defaults to 'world'."""
    click.echo(f"Hello, {name or 'world'}!")
