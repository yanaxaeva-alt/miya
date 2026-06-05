"""Local FastAPI backend for the future desktop editor."""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from threading import Condition
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel, Field

from miaos.executor import AgentGraphSpec, CheckpointStore, GraphEvent, GraphRunner
from miaos.models import MockModelProvider, ModelManager, ModelProvider, ModelRole
from miaos.models.registry import ModelNotFoundError
from miaos.observability import DecisionLog
from miaos.persona import (
    PersonaPackageError,
    create_persona_package,
    validate_persona_package,
)
from miaos.runtime import list_runtime_profiles, load_runtime_profile

TERMINAL_EVENT_TYPES = {"run_completed", "run_stopped"}


class RunEventHub:
    """Thread-safe in-process event hub for live graph run WebSockets."""

    def __init__(self) -> None:
        """Create an empty event hub."""
        self._condition = Condition()
        self._events: dict[str, list[GraphEvent]] = {}
        self._terminal_runs: set[str] = set()

    def publish(self, event: GraphEvent) -> None:
        """Publish one event and wake subscribers."""
        with self._condition:
            self._events.setdefault(event.run_id, []).append(event)
            if event.event_type.value in TERMINAL_EVENT_TYPES:
                self._terminal_runs.add(event.run_id)
            self._condition.notify_all()

    def events_after(self, run_id: str, offset: int) -> list[GraphEvent]:
        """Return events after an offset."""
        with self._condition:
            return list(self._events.get(run_id, [])[offset:])

    def is_terminal(self, run_id: str) -> bool:
        """Return whether a terminal event has been published for a run."""
        with self._condition:
            return run_id in self._terminal_runs

    def wait_for_events(
        self,
        run_id: str,
        offset: int,
        *,
        timeout_seconds: float = 30.0,
    ) -> tuple[list[GraphEvent], bool]:
        """Block until new events or a terminal state is available."""
        with self._condition:
            self._condition.wait_for(
                lambda: len(self._events.get(run_id, [])) > offset
                or run_id in self._terminal_runs,
                timeout=timeout_seconds,
            )
            return list(self._events.get(run_id, [])[offset:]), run_id in self._terminal_runs


class MiaOSApiState:
    """Mutable backend state for the local API."""

    def __init__(self, base_dir: Path, *, provider: ModelProvider | None = None) -> None:
        """Create API state rooted under a local data directory."""
        self.base_dir = base_dir
        self.model_manager = ModelManager.from_path(base_dir / "models.sqlite3")
        self.decision_log = DecisionLog(base_dir / "decisions.jsonl")
        self.checkpoint_store = CheckpointStore(base_dir / "checkpoints.sqlite3")
        self.provider = provider or MockModelProvider()
        self.persona_dir = base_dir / "personas"
        self.graph_dir = base_dir / "graphs"
        self.run_events: dict[str, list[GraphEvent]] = {}
        self.run_event_hub = RunEventHub()
        self.persona_dir.mkdir(parents=True, exist_ok=True)
        self.graph_dir.mkdir(parents=True, exist_ok=True)


class ModelRegisterPayload(BaseModel):
    """Request body for model metadata registration."""

    repo: str
    family: str
    params_billion: float
    quant: str
    size_bytes: int
    context_len: int
    path: str
    pool_role: ModelRole | None = None


class PersonaCreatePayload(BaseModel):
    """Request body for creating a minimal persona package."""

    name: str
    profile: dict[str, Any]
    package_id: str = Field(default="mia")


class GraphValidatePayload(BaseModel):
    """Request body for graph validation."""

    graph: dict[str, Any]


class GraphSavePayload(BaseModel):
    """Request body for graph save/load."""

    graph: dict[str, Any]


class GraphRunPayload(BaseModel):
    """Request body for graph execution."""

    graph: dict[str, Any]
    input_text: str
    run_id: str | None = None


def create_app(state: MiaOSApiState | None = None) -> FastAPI:
    """Create the local API application."""
    api_state = state or MiaOSApiState(Path(".miaos"))
    app = FastAPI(title="MiaOS Builder API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return API health."""
        return {"status": "ok"}

    @app.get("/runtime/profiles")
    def runtime_profiles() -> list[dict[str, Any]]:
        """Return available runtime profiles."""
        return [
            load_runtime_profile(profile_name).model_dump(mode="json")
            for profile_name in list_runtime_profiles()
        ]

    @app.get("/models")
    def models() -> list[dict[str, Any]]:
        """List registered models."""
        return [record.model_dump(mode="json") for record in api_state.model_manager.list_models()]

    @app.post("/models/register")
    def register_model(payload: ModelRegisterPayload) -> dict[str, Any]:
        """Register model metadata."""
        record = api_state.model_manager.register_model(**payload.model_dump())
        return record.model_dump(mode="json")

    @app.get("/models/{model_id}")
    def inspect_model(model_id: str) -> dict[str, Any]:
        """Inspect one model."""
        try:
            record = api_state.model_manager.inspect_model(model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model not found") from exc
        return record.model_dump(mode="json")

    @app.get("/personas")
    def personas() -> list[dict[str, Any]]:
        """List persona package manifests."""
        return [
            validate_persona_package(manifest_path.parent).model_dump(mode="json")
            for manifest_path in sorted(api_state.persona_dir.glob("*/manifest.json"))
        ]

    @app.post("/personas")
    def create_persona(payload: PersonaCreatePayload) -> dict[str, Any]:
        """Create a persona package from inline profile data."""
        profile_path = api_state.base_dir / f"{payload.package_id}.persona.yaml"
        profile_path.write_text(_dump_profile_yaml(payload.profile), encoding="utf-8")
        try:
            package = create_persona_package(
                name=payload.name,
                profile_path=profile_path,
                output_path=api_state.persona_dir / payload.package_id,
            )
        except PersonaPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return package.manifest.model_dump(mode="json")

    @app.get("/graphs")
    def graphs() -> list[str]:
        """List saved graph filenames."""
        return sorted(path.name for path in api_state.graph_dir.glob("*.json"))

    @app.get("/graphs/{graph_name}")
    def load_graph(graph_name: str) -> dict[str, Any]:
        """Load a saved graph JSON document."""
        graph_path = _safe_graph_path(api_state.graph_dir, graph_name)
        if not graph_path.exists():
            raise HTTPException(status_code=404, detail="graph not found")
        raw_graph = graph_path.read_text(encoding="utf-8")
        return AgentGraphSpec.model_validate_json(raw_graph).model_dump(mode="json")

    @app.put("/graphs/{graph_name}")
    def save_graph(graph_name: str, payload: GraphSavePayload) -> dict[str, Any]:
        """Validate and save graph JSON."""
        graph = AgentGraphSpec.model_validate(payload.graph)
        graph_path = _safe_graph_path(api_state.graph_dir, graph_name)
        graph_path.write_text(f"{graph.model_dump_json(indent=2)}\n", encoding="utf-8")
        return {"saved": True, "graph": graph.model_dump(mode="json"), "name": graph_path.name}

    @app.post("/graphs/validate")
    def validate_graph(payload: GraphValidatePayload) -> dict[str, Any]:
        """Validate graph JSON."""
        graph = AgentGraphSpec.model_validate(payload.graph)
        return {"valid": True, "graph_id": graph.graph_id, "name": graph.name}

    @app.post("/graphs/run")
    def run_graph(payload: GraphRunPayload) -> dict[str, Any]:
        """Run graph JSON with the mock provider."""
        graph = AgentGraphSpec.model_validate(payload.graph)
        runner = GraphRunner(
            provider=api_state.provider,
            checkpoint_store=api_state.checkpoint_store,
            decision_log=api_state.decision_log,
        )
        run = runner.run(
            graph,
            input_text=payload.input_text,
            run_id=payload.run_id,
            event_sink=api_state.run_event_hub.publish,
        )
        api_state.run_events[run.run_id] = run.events
        return run.model_dump(mode="json")

    @app.websocket("/runs/{run_id}/events")
    async def run_events(websocket: WebSocket, run_id: str) -> None:
        """Stream live run events, falling back to replay for completed runs."""
        await websocket.accept()
        replay_events = _replay_events(api_state, run_id)
        if replay_events:
            await _send_events(websocket, replay_events)
            if _has_terminal_event(replay_events):
                await websocket.close()
                return

        offset = len(replay_events)
        while True:
            events, terminal = await asyncio.to_thread(
                api_state.run_event_hub.wait_for_events,
                run_id,
                offset,
            )
            if events:
                await _send_events(websocket, events)
                offset += len(events)
            if terminal and not api_state.run_event_hub.events_after(run_id, offset):
                break
        await websocket.close()

    @app.get("/traces/{trace_id}")
    def trace(trace_id: str) -> dict[str, Any]:
        """Return decision log events for a trace id."""
        events = [
            event.model_dump(mode="json")
            for event in api_state.decision_log.list_events()
            if event.trace_id == trace_id
        ]
        return {"trace_id": trace_id, "events": events}

    return app


def _dump_profile_yaml(profile: dict[str, Any]) -> str:
    """Serialize profile data without adding a public YAML dependency to API callers."""
    return yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)


def _safe_graph_path(graph_dir: Path, graph_name: str) -> Path:
    """Return a saved graph path, rejecting traversal and unsafe names."""
    name = graph_name if graph_name.endswith(".json") else f"{graph_name}.json"
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not name or any(char not in allowed_chars for char in name) or ".." in name:
        raise HTTPException(status_code=400, detail="invalid graph name")
    path = (graph_dir / name).resolve(strict=False)
    graph_root = graph_dir.resolve(strict=False)
    try:
        path.relative_to(graph_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid graph name") from exc
    return path


def _replay_events(api_state: MiaOSApiState, run_id: str) -> list[GraphEvent]:
    """Return replay events known before a WebSocket subscribes."""
    hub_events = api_state.run_event_hub.events_after(run_id, 0)
    if hub_events:
        return hub_events
    return api_state.run_events.get(run_id) or api_state.checkpoint_store.list_events(run_id)


async def _send_events(websocket: WebSocket, events: Sequence[GraphEvent]) -> None:
    """Send graph events as JSON messages."""
    for event in events:
        await websocket.send_json(event.model_dump(mode="json"))


def _has_terminal_event(events: Sequence[GraphEvent]) -> bool:
    """Return whether a sequence includes a terminal event."""
    return any(event.event_type.value in TERMINAL_EVENT_TYPES for event in events)


app = create_app()
