"""Command-line interface for MiaOS Builder."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from miaos import __version__
from miaos.executor import AgentGraphSpec, CheckpointStore, GraphRunner
from miaos.models import (
    MLXModelProvider,
    MockModelProvider,
    ModelManager,
    ModelNotFoundError,
    ModelProvider,
    ModelRole,
    provider_infos,
)
from miaos.observability import DecisionLog
from miaos.persona import (
    PersonaPackageError,
    create_persona_package,
    load_persona_package,
    validate_persona_package,
)
from miaos.runtime import RuntimeProfileError, list_runtime_profiles, load_runtime_profile
from miaos.runtime.chat import ChatSession
from miaos.safety import ActionRequest, PolicyGate
from miaos.tools import ToolInputError, ToolRegistry

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
safety_app = typer.Typer(help="Evaluate action requests through the Policy Gate.")
graph_app = typer.Typer(help="Validate and run AgentGraph specifications.")
tool_app = typer.Typer(help="Run sandbox-only tools through Policy Gate.")
app.add_typer(runtime_app, name="runtime")
app.add_typer(model_app, name="model")
app.add_typer(persona_app, name="persona")
app.add_typer(safety_app, name="safety")
app.add_typer(graph_app, name="graph")
app.add_typer(tool_app, name="tool")
DEFAULT_MODEL_DB_PATH = Path(".miaos") / "models.sqlite3"
DEFAULT_DECISION_LOG_PATH = Path(".miaos") / "decisions.jsonl"
DEFAULT_CHECKPOINT_DB_PATH = Path(".miaos") / "checkpoints.sqlite3"
DEFAULT_SANDBOX_ROOT = Path(".miaos") / "sandbox"


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


@safety_app.command("check")
def safety_check(
    action_path: Annotated[Path, typer.Argument(help="Path to an action request JSON file.")],
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Path to append decisions.jsonl events."),
    ] = DEFAULT_DECISION_LOG_PATH,
) -> None:
    """Evaluate an action request, append an audit decision, and print the decision."""
    try:
        request = ActionRequest.model_validate_json(action_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        error_console.print(f"Error: invalid action request: {exc}", style="red")
        raise typer.Exit(code=1) from exc

    decision = PolicyGate().evaluate(request)
    DecisionLog(log_path).append_policy_decision(decision)
    console.print(decision.model_dump_json(indent=2))


@tool_app.command("list")
def tool_list(
    sandbox_root: Annotated[
        Path,
        typer.Option("--sandbox-root", help="Sandbox root for path-scoped tools."),
    ] = DEFAULT_SANDBOX_ROOT,
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Path to append decisions.jsonl events."),
    ] = DEFAULT_DECISION_LOG_PATH,
) -> None:
    """List sandbox-only tools."""
    registry = ToolRegistry(sandbox_root=sandbox_root, decision_log=DecisionLog(log_path))
    table = Table(title="Sandbox tools")
    table.add_column("Name")
    table.add_column("Action")
    table.add_column("Description")
    for spec in registry.list_tools():
        table.add_row(spec.name, spec.action_class.value, spec.description)
    console.print(table)


@tool_app.command("run")
def tool_run(
    tool_name: Annotated[str, typer.Argument(help="Tool name to execute.")],
    args_json: Annotated[
        str,
        typer.Option("--args-json", help="Tool arguments as a JSON object."),
    ],
    sandbox_root: Annotated[
        Path,
        typer.Option("--sandbox-root", help="Sandbox root for path-scoped tools."),
    ] = DEFAULT_SANDBOX_ROOT,
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Path to append decisions.jsonl events."),
    ] = DEFAULT_DECISION_LOG_PATH,
) -> None:
    """Run a sandbox tool through Policy Gate and append audit events."""
    try:
        raw_arguments = json.loads(args_json)
    except json.JSONDecodeError as exc:
        error_console.print(f"Error: invalid --args-json: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    if not isinstance(raw_arguments, dict):
        error_console.print("Error: --args-json must decode to a JSON object", style="red")
        raise typer.Exit(code=1)

    arguments = dict[str, object](raw_arguments)
    registry = ToolRegistry(sandbox_root=sandbox_root, decision_log=DecisionLog(log_path))
    try:
        result = registry.run(tool_name, arguments)
    except ToolInputError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    console.print(result.model_dump_json(indent=2))


@app.command("chat")
def chat(
    persona: Annotated[Path, typer.Option("--persona", help="Path to a `.mia` persona package.")],
    provider_name: Annotated[
        str,
        typer.Option("--provider", help="Model provider name: mock or mlx."),
    ] = "mock",
    messages: Annotated[
        list[str] | None,
        typer.Option("--message", "-m", help="Message to send. Repeat for multiple turns."),
    ] = None,
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Path to append decisions.jsonl events."),
    ] = DEFAULT_DECISION_LOG_PATH,
) -> None:
    """Run a non-interactive chat session through the runtime vertical slice."""
    if not messages:
        error_console.print(
            "Error: provide at least one --message for non-interactive chat",
            style="red",
        )
        raise typer.Exit(code=1)

    try:
        persona_package = load_persona_package(persona)
    except PersonaPackageError as exc:
        error_console.print(f"Error: {exc}", style="red")
        raise typer.Exit(code=1) from exc

    provider = _provider_from_name(provider_name)
    session = ChatSession(
        persona=persona_package,
        provider=provider,
        decision_log=DecisionLog(log_path),
    )
    for message in messages:
        turn = session.run_turn(message)
        console.print(f"[{turn.trace_id}] {turn.response_text}", markup=False)


def _provider_from_name(provider_name: str) -> ModelProvider:
    """Resolve a provider name to a provider instance."""
    if provider_name == "mock":
        return MockModelProvider()
    if provider_name == "mlx":
        provider = MLXModelProvider()
        if not provider.is_available():
            error_console.print(
                "Error: MLX provider is unavailable; install mlx-lm or use --provider mock",
                style="red",
            )
            raise typer.Exit(code=1)
        return provider
    error_console.print(f"Error: unknown provider {provider_name!r}", style="red")
    raise typer.Exit(code=1)


@graph_app.command("validate")
def graph_validate(
    graph_path: Annotated[Path, typer.Argument(help="Path to an AgentGraph JSON file.")],
) -> None:
    """Validate an AgentGraph JSON file."""
    try:
        graph = _load_graph(graph_path)
    except ValueError as exc:
        error_console.print(f"Error: invalid graph: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    console.print(f"Graph is valid: {graph.name} ({graph.graph_id})")


@graph_app.command("run")
def graph_run(
    graph_path: Annotated[Path, typer.Argument(help="Path to an AgentGraph JSON file.")],
    input_text: Annotated[str, typer.Option("--input", help="Input text for the graph.")],
    provider_name: Annotated[
        str,
        typer.Option("--provider", help="Model provider name: mock or mlx."),
    ] = "mock",
    log_path: Annotated[
        Path,
        typer.Option("--log", help="Path to append decisions.jsonl events."),
    ] = DEFAULT_DECISION_LOG_PATH,
    checkpoint_db: Annotated[
        Path,
        typer.Option("--checkpoint-db", help="SQLite checkpoint store path."),
    ] = DEFAULT_CHECKPOINT_DB_PATH,
) -> None:
    """Run an AgentGraph with the selected provider."""
    try:
        graph = _load_graph(graph_path)
    except ValueError as exc:
        error_console.print(f"Error: invalid graph: {exc}", style="red")
        raise typer.Exit(code=1) from exc
    runner = GraphRunner(
        provider=_provider_from_name(provider_name),
        checkpoint_store=CheckpointStore(checkpoint_db),
        decision_log=DecisionLog(log_path),
    )
    run = runner.run(graph, input_text=input_text)
    console.print(run.model_dump_json(indent=2))


def _load_graph(graph_path: Path) -> AgentGraphSpec:
    """Load a graph specification from JSON."""
    return AgentGraphSpec.model_validate_json(graph_path.read_text(encoding="utf-8"))
