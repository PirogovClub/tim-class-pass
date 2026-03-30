"""MDRT CLI — Typer entry point.

This module defines the ``mdrt`` command-line application.
Individual commands (ingest-bars, build-window, etc.) are added by later tickets.
"""

import typer

app = typer.Typer(
    name="mdrt",
    help="Market Data Retrieval Tool — historical OHLCV archive and window builder.",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    """Market Data Retrieval Tool — historical OHLCV archive and window builder."""
    if version:
        typer.echo("mdrt 0.1.0")
        raise typer.Exit()
