"""Command-line interface for AEON without GCS."""

import json
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from aeon import __version__
from aeon.config import load_aeon_config
from aeon.paths import resolve_data_dir
from aeon.runtime import AeonRuntime
from aeon.types import AeonRequest

app = typer.Typer(
    add_completion=False,
    help="AEON local runtime without Generative Cognitive Substrate.",
    no_args_is_help=True,
)
goals_app = typer.Typer(no_args_is_help=True, help="Manage AEON goals.")
app.add_typer(goals_app, name="goals")
console = Console()
error_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"aeon {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            help="Show the AEON version and exit.",
        ),
    ] = False,
) -> None:
    """Run AEON commands."""


def _runtime(data_dir: Path | None, config_path: Path | None) -> AeonRuntime:
    config = load_aeon_config(config_path) if config_path else load_aeon_config()
    return AeonRuntime(base_dir=resolve_data_dir(data_dir), config=config)


@app.command()
def version_cmd() -> None:
    """Print the AEON version."""
    console.print(f"aeon {__version__}")


@app.command()
def status(
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="MiaOS/AEON data directory (default: MIYA_DATA_DIR or .miaos)."),
    ] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
) -> None:
    """Show identity, goals, and recent memory."""
    runtime = _runtime(data_dir, config)
    payload = runtime.status()

    table = Table(title="AEON status")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Data dir", str(resolve_data_dir(data_dir)))
    table.add_row("Identity", str(payload["identity"]))
    table.add_row("Provider", str(payload["provider"]))
    table.add_row("Values", ", ".join(payload["values"]))  # type: ignore[arg-type]
    console.print(table)

    goals = payload["active_goals"]
    if goals:
        goal_table = Table(title="Active goals")
        goal_table.add_column("ID")
        goal_table.add_column("Title")
        goal_table.add_column("Priority")
        goal_table.add_column("Progress")
        for goal in goals:
            goal_table.add_row(
                str(goal["id"]),
                str(goal["title"]),
                f"{goal['priority']:.2f}",
                f"{goal['progress']:.2f}",
            )
        console.print(goal_table)


@app.command()
def tick(
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
) -> None:
    """Run one Active Inference heartbeat."""
    runtime = _runtime(data_dir, config)
    result = runtime.tick()
    console.print_json(json.dumps(result))


@app.command()
def ask(
    message: Annotated[str, typer.Argument(help="User message for AEON.")],
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
    graph: Annotated[bool, typer.Option("--graph", help="Force fixed graph execution.")] = False,
) -> None:
    """Ask AEON a question through all non-GCS layers."""
    runtime = _runtime(data_dir, config)
    response = runtime.ask(AeonRequest(message=message, force_graph=graph))
    console.print(response.text)
    if response.blocked:
        raise typer.Exit(code=2)
    console.print(
        f"[dim]trace={response.trace_id} mode={response.execution_mode.value}"
        f"{f' graph={response.graph_id}' if response.graph_id else ''}[/dim]"
    )


@goals_app.command("add")
def goals_add(
    title: Annotated[str, typer.Argument(help="Goal title.")],
    description: Annotated[str, typer.Argument(help="Goal description.")],
    priority: Annotated[float, typer.Option("--priority", min=0.0, max=1.0)] = 0.6,
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
) -> None:
    """Add one user goal to the AEON goal pool."""
    runtime = _runtime(data_dir, config)
    goal = runtime.add_goal(title=title, description=description, priority=priority)
    console.print_json(json.dumps(goal.model_dump(mode="json")))


@goals_app.command("deactivate")
def goals_deactivate(
    goal_id: Annotated[str, typer.Argument(help="Goal id to deactivate.")],
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
) -> None:
    """Deactivate one goal in the AEON goal pool."""
    runtime = _runtime(data_dir, config)
    if not runtime.deactivate_goal(goal_id):
        error_console.print(f"Goal not found: {goal_id}")
        raise typer.Exit(code=1)
    console.print(f"Deactivated goal {goal_id}")


@app.command()
def consolidate(
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
) -> None:
    """Run morning-style consolidation for goals and memory."""
    runtime = _runtime(data_dir, config)
    result = runtime.consolidate()
    console.print_json(json.dumps(result))


@app.command()
def daemon(
    data_dir: Annotated[Path | None, typer.Option("--data-dir", help="MiaOS/AEON data directory.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Optional AEON config path.")] = None,
    once: Annotated[bool, typer.Option("--once", help="Run a single heartbeat and exit.")] = False,
    interval: Annotated[int | None, typer.Option("--interval", help="Override heartbeat interval.")] = None,
) -> None:
    """Run the always-on heartbeat loop."""
    runtime = _runtime(data_dir, config)
    sleep_seconds = interval or runtime.config.heartbeat.interval_seconds
    console.print(
        f"AEON heartbeat started (data={resolve_data_dir(data_dir)}, interval={sleep_seconds}s). Ctrl+C to stop."
    )
    try:
        while True:
            result = runtime.tick()
            console.print(
                f"tick={result['tick_id']} surprise={result['surprise']} action={result['action']}"
            )
            if once:
                break
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        console.print("AEON heartbeat stopped.")


if __name__ == "__main__":
    app()
