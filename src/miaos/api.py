"""Local FastAPI backend for the future desktop editor."""

from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from miaos.executor import AgentGraphSpec, CheckpointStore, GraphEvent, GraphRunner
from miaos.models import ModelManager, ModelRole
from miaos.models.providers import MockModelProvider
from miaos.models.registry import ModelNotFoundError
from miaos.observability import DecisionLog
from miaos.persona import (
    PersonaPackageError,
    create_persona_package,
    validate_persona_package,
)
from miaos.runtime import list_runtime_profiles, load_runtime_profile

DEV_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


class MiaOSApiState:
    """Mutable backend state for the local API."""

    def __init__(self, base_dir: Path) -> None:
        """Create API state rooted under a local data directory."""
        self.base_dir = base_dir
        self.model_manager = ModelManager.from_path(base_dir / "models.sqlite3")
        self.decision_log = DecisionLog(base_dir / "decisions.jsonl")
        self.checkpoint_store = CheckpointStore(base_dir / "checkpoints.sqlite3")
        self.persona_dir = base_dir / "personas"
        self.graph_dir = base_dir / "graphs"
        self.run_events: dict[str, list[GraphEvent]] = {}
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


class GraphRunPayload(BaseModel):
    """Request body for graph execution."""

    graph: dict[str, Any]
    input_text: str


def create_app(state: MiaOSApiState | None = None) -> FastAPI:
    """Create the local API application."""
    api_state = state or MiaOSApiState(Path(".miaos"))
    app = FastAPI(title="MiaOS Builder API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            provider=MockModelProvider(),
            checkpoint_store=api_state.checkpoint_store,
            decision_log=api_state.decision_log,
        )
        run = runner.run(graph, input_text=payload.input_text)
        api_state.run_events[run.run_id] = run.events
        return run.model_dump(mode="json")

    @app.websocket("/runs/{run_id}/events")
    async def run_events(websocket: WebSocket, run_id: str) -> None:
        """Send stored run events over a WebSocket and close."""
        await websocket.accept()
        events = api_state.run_events.get(run_id) or api_state.checkpoint_store.list_events(run_id)
        for event in events:
            await websocket.send_json(event.model_dump(mode="json"))
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


app = create_app()
