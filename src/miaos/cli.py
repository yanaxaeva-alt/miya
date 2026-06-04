"""Command-line interface for MiaOS Builder."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from miaos import __version__
from miaos.models import ModelManager, ModelNotFoundError, ModelRole, provider_infos
from miaos.persona import (
    PersonaPackageError,
    create_persona_package,
    validate_persona_package,
)
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
persona_app = typer.Typer(help="Create, inspect, and validate `.mia` persona packages.")
app.add_typer(runtime_app, name="runtime")
app.add_typer(model_app, name="model")
app.add_typer(persona_app, name="persona")
DEFAULT_MODEL_DB_PATH = Path(".miaos") / "models.sqlite3"


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


@model_app.command("register")
def model_register(
    repo: Annotated[str, typer.Option("--repo", help="Model repository or local identifier.")],
    family: Annotated[str, typer.Option("--family", help="Model family, for example qwen.")],
    params_billion: Annotated[
        float,
        typer.Option("--params-billion", help="Total model parameters in billions."),
    ],
    quant: Annotated[str, typer.Option("--quant", help="Quantization label.")],
    size_bytes: Annotated[int, typer.Option("--size-bytes", help="Model size in bytes.")],
    context_len: Annotated[int, typer.Option("--context-len", help="Context window length.")],
    path: Annotated[str, typer.Option("--path", help="Local model path or cache reference.")],
    active_params_billion: Annotated[
        float | None,
        typer.Option("--active-params-billion", help="Active MoE parameters in billions."),
    ] = None,
    is_moe: Annotated[bool, typer.Option("--moe", help="Mark the model as MoE.")] = False,
    pool_role: Annotated[
        ModelRole | None,
        typer.Option("--pool-role", help="Optional model pool role."),
    ] = None,
    checksum_sha256: Annotated[
        str | None,
        typer.Option("--checksum-sha256", help="Optional SHA-256 metadata."),
    ] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Optional registry notes.")] = None,
    db_path: Annotated[
        Path,
        typer.Option("--db", help="SQLite model registry path."),
    ] = DEFAULT_MODEL_DB_PATH,
) -> None:
    """Register model metadata in the local SQLite registry."""
    manager = ModelManager.from_path(db_path)
    record = manager.register_model(
        repo=repo,
        family=family,
        params_billion=params_billion,
        active_params_billion=active_params_billion,
        is_moe=is_moe,
        quant=quant,
        size_bytes=size_bytes,
        context_len=context_len,
        path=path,
        pool_role=pool_role,
        checksum_sha256=checksum_sha256,
        notes=notes,
    )
    console.print(record.model_dump_json(indent=2))


@model_app.command("list")
def model_list(
    db_path: Annotated[
        Path,
        typer.Option("--db", help="SQLite model registry path."),
    ] = DEFAULT_MODEL_DB_PATH,
) -> None:
    """List registered model metadata."""
    manager = ModelManager.from_path(db_path)
    records = manager.list_models()
    table = Table(title="Registered models")
    table.add_column("ID")
    table.add_column("Repo")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("Lab")
    for record in records:
        table.add_row(
            record.id,
            record.repo,
            record.pool_role.value if record.pool_role else "-",
            record.status.value,
            record.lab_cert.value if record.lab_cert else "-",
        )
    console.print(table)


@model_app.command("inspect")
def model_inspect(
    model_id: Annotated[str, typer.Argument(help="Model registry id.")],
    db_path: Annotated[
        Path,
        typer.Option("--db", help="SQLite model registry path."),
    ] = DEFAULT_MODEL_DB_PATH,
) -> None:
    """Inspect one registered model record."""
    manager = ModelManager.from_path(db_path)
    try:
        record = manager.inspect_model(model_id)
    except ModelNotFoundError as exc:
        error_console.print(f"Error: model {model_id!r} not found", style="red")
        raise typer.Exit(code=1) from exc
    console.print(record.model_dump_json(indent=2))


@persona_app.command("create")
def persona_create(
    name: Annotated[str, typer.Option("--name", help="Persona name.")],
    profile: Annotated[Path, typer.Option("--profile", help="Persona profile YAML path.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Output `.mia` directory. Defaults to profile parent."),
    ] = None,
) -> None:
    """Create a minimal directory-based `.mia` persona package."""
    try:
        package = create_persona_package(name=name, profile_path=profile, output_path=output)
    except PersonaPackageError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    console.print(package.manifest.model_dump_json(indent=2))


@persona_app.command("inspect")
def persona_inspect(
    path: Annotated[Path, typer.Argument(help="Path to a `.mia` directory package.")],
) -> None:
    """Inspect a `.mia` persona package manifest."""
    try:
        manifest = validate_persona_package(path)
    except PersonaPackageError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    console.print(manifest.model_dump_json(indent=2))


@persona_app.command("validate")
def persona_validate(
    path: Annotated[Path, typer.Argument(help="Path to a `.mia` directory package.")],
) -> None:
    """Validate a `.mia` persona package."""
    try:
        manifest = validate_persona_package(path)
    except PersonaPackageError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    console.print(f"Persona package is valid: {manifest.name} ({manifest.persona_id})")
