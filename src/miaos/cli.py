"""Command-line interface for MiaOS Builder."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from miaos import __version__
from miaos.models import provider_infos
from miaos.runtime import RuntimeProfileError, list_runtime_profiles, load_runtime_profile

app = typer.Typer(
    add_completion=False,
    help="MiaOS Builder local runtime CLI.",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True)
runtime_app = typer.Typer(help="Inspect hardware-aware runtime profiles.")
model_app = typer.Typer(help="Inspect model provider and registry state.")
app.add_typer(runtime_app, name="runtime")
app.add_typer(model_app, name="model")


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


@runtime_app.command("profiles")
def runtime_profiles() -> None:
    """List available runtime profiles."""
    profiles = list_runtime_profiles()
    if not profiles:
        console.print("No runtime profiles found.")
        return

    table = Table(title="Runtime profiles")
    table.add_column("Name")
    for profile_name in profiles:
        table.add_row(profile_name)
    console.print(table)


@runtime_app.command("inspect")
def runtime_inspect(
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Runtime profile name to inspect."),
    ],
) -> None:
    """Print a validated runtime profile as JSON."""
    try:
        runtime_profile = load_runtime_profile(profile)
    except RuntimeProfileError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc

    console.print_json(runtime_profile.model_dump_json(indent=2))


@model_app.command("providers")
def model_providers() -> None:
    """List known model providers and their availability."""
    table = Table(title="Model providers")
    table.add_column("Name")
    table.add_column("Available")
    table.add_column("Description")
    for provider in provider_infos():
        table.add_row(provider.name, "yes" if provider.available else "no", provider.description)
    console.print(table)
