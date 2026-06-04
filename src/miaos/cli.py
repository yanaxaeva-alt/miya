"""Command-line interface for MiaOS Builder."""

from typing import Annotated

import typer
from rich.console import Console

from miaos import __version__

app = typer.Typer(
    add_completion=False,
    help="MiaOS Builder local runtime CLI.",
    no_args_is_help=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"miaos {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the MiaOS Builder version and exit.",
        ),
    ] = False,
) -> None:
    """Run MiaOS Builder commands."""


@app.command()
def version() -> None:
    """Print the MiaOS Builder version."""
    console.print(f"miaos {__version__}")
