"""Local FastAPI backend for the future desktop editor."""

import json
from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from aeon import __version__ as aeon_version
from aeon.config import load_aeon_config
from aeon.paths import resolve_data_dir
from aeon.runtime import AeonRuntime
from aeon.types import AeonRequest
from miaos import __version__ as miaos_version
from miaos.executor import AgentGraphSpec, CheckpointStore, GraphEvent, GraphRunner
from miaos.memory import MemoryStore
from miaos.models import (
    LabCertificationStatus,
    ModelManager,
    ModelRole,
    evaluate_models_for_profile,
)
from miaos.models.providers import (
    OMLXModelProvider,
    default_provider_name,
    provider_infos,
    resolve_provider,
)
from miaos.models.registry import ModelNotFoundError
from miaos.observability import DecisionLog
from miaos.persona import (
    PersonaPackageError,
    create_persona_package,
    export_persona_archive,
    import_persona_archive,
    load_persona_package,
    update_persona_model_binding,
)
from miaos.quality import list_datasets, load_dataset, run_quality_eval
from miaos.runtime import RuntimeProfileError, list_runtime_profiles, load_runtime_profile
from miaos.runtime.chat import ChatSession
from miaos.safety.approval_queue import ApprovalQueue, ApprovalStatus
from miaos.settings import RuntimeSettingsStore, apply_runtime_settings, runtime_settings_path
from miaos.templates import (
    TemplateNotFoundError,
    get_template,
    instantiate_template,
    list_templates,
)
from miaos.tools import list_tools

DEV_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


class MiaOSApiState:
    """Mutable backend state for the local API."""

    def __init__(self, base_dir: Path) -> None:
        """Create API state rooted under a local data directory."""
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.settings_store = RuntimeSettingsStore(runtime_settings_path(base_dir))
        apply_runtime_settings(self.settings_store.load())
        self.model_manager = ModelManager.from_path(base_dir / "models.sqlite3")
        self.decision_log = DecisionLog(base_dir / "decisions.jsonl")
        self.approval_queue = ApprovalQueue(self.decision_log)
        self.checkpoint_store = CheckpointStore(base_dir / "checkpoints.sqlite3")
        self.memory_store = MemoryStore(base_dir / "memory.sqlite3")
        self.persona_dir = base_dir / "personas"
        self.graph_dir = base_dir / "graphs"
        self.run_events: dict[str, list[GraphEvent]] = {}
        self._aeon_runtimes: dict[str, AeonRuntime] = {}
        self.persona_dir.mkdir(parents=True, exist_ok=True)
        self.graph_dir.mkdir(parents=True, exist_ok=True)

    def get_aeon_runtime(
        self,
        *,
        provider: str | None = None,
        package_id: str = "mia",
    ) -> AeonRuntime:
        """Return a cached AEON runtime for stable goal pool and heartbeat state."""
        config = load_aeon_config()
        provider_name = provider or config.provider
        cache_key = f"{package_id}:{provider_name}"
        if cache_key not in self._aeon_runtimes:
            self._aeon_runtimes[cache_key] = AeonRuntime(
                base_dir=self.base_dir,
                config=config.model_copy(
                    update={"persona_package_id": package_id, "provider": provider_name}
                ),
                approval_queue=self.approval_queue,
            )
        return self._aeon_runtimes[cache_key]

    def clear_aeon_runtime_cache(self) -> None:
        """Drop cached AEON runtimes after persona/provider settings change."""
        self._aeon_runtimes.clear()


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


class ModelLabCertPayload(BaseModel):
    """Request body for updating model lab certification."""

    lab_cert: LabCertificationStatus | None = None


class ProviderDefaultModelPayload(BaseModel):
    """Request body for selecting a provider default model."""

    model_id: str = Field(min_length=1)


class PersonaModelBindingPayload(BaseModel):
    """Request body for updating persona model binding."""

    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


DEMO_MODEL_REPOS = [
    "qwen3.5-8b",
    "qwen3.5-14b-pro-65k",
    "qwen3.5-coder-7b",
    "qwen3.5-4b",
]


class PersonaCreatePayload(BaseModel):
    """Request body for creating a minimal persona package."""

    name: str
    profile: dict[str, Any]
    package_id: str = Field(default="mia")


class GraphValidatePayload(BaseModel):
    """Request body for graph validation."""

    graph: dict[str, Any]


class GraphSavePayload(BaseModel):
    """Request body for saving a graph spec to disk."""

    graph: dict[str, Any]
    filename: str | None = None


class TemplateInstantiatePayload(BaseModel):
    """Request body for creating a graph from a template."""

    graph_id: str | None = None
    name: str | None = None


class GraphRunPayload(BaseModel):
    """Request body for graph execution."""

    graph: dict[str, Any]
    input_text: str
    provider: str = Field(default_factory=default_provider_name)


class ApprovalResolvePayload(BaseModel):
    """Request body for resolving a queued approval."""

    decision: str
    actor: str = "human"


class ChatPayload(BaseModel):
    """Request body for one persona chat turn."""

    message: str = Field(min_length=1)
    package_id: str = Field(default="mia", min_length=1)
    provider: str = Field(default_factory=default_provider_name)


class QualityEvalPayload(BaseModel):
    """Request body for running a golden dataset eval."""

    dataset: str = Field(default="golden_mvp", min_length=1)
    provider: str = Field(default_factory=default_provider_name)
    package_id: str = Field(default="mia", min_length=1)


class MemoryEpisodePayload(BaseModel):
    """Request body for storing one episodic memory."""

    package_id: str = Field(default="mia", min_length=1)
    content: str = Field(min_length=1)
    role: str = "assistant"
    trace_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ProfileFactPayload(BaseModel):
    """Request body for upserting a profile fact."""

    package_id: str = Field(default="mia", min_length=1)
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class DomainNotePayload(BaseModel):
    """Request body for storing a domain note."""

    package_id: str = Field(default="mia", min_length=1)
    domain: str = Field(default="general", min_length=1)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class AeonAskPayload(BaseModel):
    """Request body for one AEON ask turn."""

    message: str = Field(min_length=1)
    provider: str = Field(default_factory=default_provider_name)
    force_graph: bool = False
    package_id: str = Field(default="mia", min_length=1)


class AeonGoalPayload(BaseModel):
    """Request body for adding a user goal to AEON."""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: float = Field(default=0.6, ge=0.0, le=1.0)
    package_id: str = Field(default="mia", min_length=1)
    provider: str = Field(default_factory=default_provider_name)


def _persona_package_response(package_path: Path) -> dict[str, Any]:
    """Return persona manifest metadata plus runtime-visible model binding."""
    package = load_persona_package(package_path)
    body = package.manifest.model_dump(mode="json")
    body["package_id"] = package.root.name
    body["model_binding"] = package.model_binding.model_dump(mode="json")
    return body


def create_app(state: MiaOSApiState | None = None) -> FastAPI:  # noqa: PLR0915
    """Create the local API application."""
    api_state = state or MiaOSApiState(resolve_data_dir())
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

    @app.get("/api/status")
    def api_status() -> dict[str, Any]:
        """Unified status for editor probes and direct backend checks."""
        return {
            "status": "ok",
            "service": "miaos-builder",
            "version": miaos_version,
            "aeon_version": aeon_version,
            "endpoints": {
                "health": "/health",
                "aeon_status": "/aeon/status",
                "aeon_ask": "/aeon/ask",
                "aeon_tick": "/aeon/tick",
                "aeon_goals": "/aeon/goals",
                "aeon_goals_deactivate": "/aeon/goals/{goal_id}/deactivate",
                "aeon_consolidate": "/aeon/consolidate",
            },
        }

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

    @app.delete("/models/demo")
    def delete_demo_models() -> dict[str, Any]:
        """Delete demo model records by known repo identifiers."""
        deleted = api_state.model_manager.delete_by_repos(DEMO_MODEL_REPOS)
        return {"status": "ok", "deleted": deleted, "repos": DEMO_MODEL_REPOS}

    @app.get("/models/compatibility")
    def model_compatibility(
        profile_name: str,
        role: ModelRole = ModelRole.WORKER,
    ) -> list[dict[str, Any]]:
        """Return compatibility warnings for all models against a runtime profile."""
        try:
            profile = load_runtime_profile(profile_name)
        except RuntimeProfileError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        selected = api_state.model_manager.select_model_for_profile(profile, role=role)
        reports = evaluate_models_for_profile(
            api_state.model_manager.list_models(),
            profile,
            role=role,
            recommended_model_id=selected.id if selected else None,
        )
        return [report.model_dump(mode="json") for report in reports]

    @app.get("/models/{model_id}")
    def inspect_model(model_id: str) -> dict[str, Any]:
        """Inspect one model."""
        try:
            record = api_state.model_manager.inspect_model(model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model not found") from exc
        return record.model_dump(mode="json")

    @app.patch("/models/{model_id}/lab-cert")
    def set_model_lab_cert(model_id: str, payload: ModelLabCertPayload) -> dict[str, Any]:
        """Update lab certification metadata for one model."""
        try:
            record = api_state.model_manager.set_lab_cert(model_id, payload.lab_cert)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail="model not found") from exc
        return record.model_dump(mode="json")

    @app.get("/personas")
    def personas() -> list[dict[str, Any]]:
        """List persona package manifests."""
        return [
            _persona_package_response(manifest_path.parent)
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
        return _persona_package_response(package.root)

    @app.patch("/personas/{package_id}/model-binding")
    def set_persona_model_binding(
        package_id: str,
        payload: PersonaModelBindingPayload,
    ) -> dict[str, Any]:
        """Update one persona package model binding."""
        package_path = api_state.persona_dir / package_id
        if not package_path.is_dir():
            raise HTTPException(status_code=404, detail="persona package not found")
        try:
            package = update_persona_model_binding(
                package_path,
                provider=payload.provider,
                model_id=payload.model_id,
            )
        except PersonaPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        api_state.clear_aeon_runtime_cache()
        return _persona_package_response(package.root)

    @app.get("/personas/{package_id}/export")
    def export_persona(package_id: str) -> Response:
        """Export one persona package as a portable `.mia.zip` archive."""
        package_path = api_state.persona_dir / package_id
        if not package_path.is_dir():
            raise HTTPException(status_code=404, detail="persona package not found")
        try:
            archive = export_persona_archive(package_path)
        except PersonaPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        filename = f"{package_id}.mia.zip"
        return Response(
            content=archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/personas/import")
    async def import_persona(
        file: Annotated[UploadFile, File()],
        package_id: Annotated[str | None, Form()] = None,
        overwrite: Annotated[bool, Form()] = False,  # noqa: FBT002
    ) -> dict[str, Any]:
        """Import a `.mia.zip` persona archive into the local persona directory."""
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="upload is empty")
        try:
            package = import_persona_archive(
                payload,
                api_state.persona_dir,
                package_id=package_id,
                overwrite=overwrite,
            )
        except PersonaPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _persona_package_response(package.root)

    @app.get("/providers")
    def providers() -> list[dict[str, Any]]:
        """List model providers and availability."""
        return [info.model_dump(mode="json") for info in provider_infos()]

    @app.post("/providers/omlx/default-model")
    def set_omlx_default_model(payload: ProviderDefaultModelPayload) -> list[dict[str, Any]]:
        """Select the active oMLX model for subsequent local inference calls."""
        provider = OMLXModelProvider()
        if not provider.is_available():
            raise HTTPException(status_code=400, detail="oMLX server is unavailable")
        model_ids = provider.list_model_ids()
        if payload.model_id not in model_ids:
            raise HTTPException(status_code=404, detail=f"unknown oMLX model: {payload.model_id}")
        settings = api_state.settings_store.select_model(
            provider="omlx",
            model_id=payload.model_id,
            base_url=provider.base_url,
        )
        apply_runtime_settings(settings, override=True)
        mia_path = api_state.persona_dir / "mia"
        if mia_path.is_dir():
            update_persona_model_binding(
                mia_path,
                provider="omlx",
                model_id=payload.model_id,
            )
            api_state.clear_aeon_runtime_cache()
        return [info.model_dump(mode="json") for info in provider_infos()]

    @app.get("/tools")
    def tools() -> list[dict[str, Any]]:
        """Return sandbox tool registry entries."""
        return [tool.model_dump(mode="json") for tool in list_tools()]

    @app.get("/quality/datasets")
    def quality_datasets() -> list[dict[str, Any]]:
        """List golden eval datasets."""
        return list_datasets()

    @app.post("/quality/eval")
    def quality_eval(payload: QualityEvalPayload) -> dict[str, Any]:
        """Run a deterministic golden dataset eval with the selected provider."""
        try:
            dataset = load_dataset(payload.dataset)
            resolve_provider(payload.provider)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            report = run_quality_eval(
                dataset,
                provider_name=payload.provider,
                persona_dir=api_state.persona_dir,
                package_id=payload.package_id,
                decision_log=api_state.decision_log,
                checkpoint_store=api_state.checkpoint_store,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return report.model_dump(mode="json")

    @app.get("/memory/summary")
    def memory_summary(package_id: str = "mia") -> dict[str, Any]:
        """Return memory counts for one persona package."""
        return {"package_id": package_id, **api_state.memory_store.summary(package_id)}

    @app.get("/memory/episodes")
    def memory_episodes(package_id: str = "mia") -> list[dict[str, Any]]:
        """List episodic memories for a persona package."""
        return [
            episode.model_dump(mode="json")
            for episode in api_state.memory_store.list_episodes(package_id)
        ]

    @app.post("/memory/episodes")
    def memory_add_episode(payload: MemoryEpisodePayload) -> dict[str, Any]:
        """Append one episodic memory record."""
        episode = api_state.memory_store.add_episode(
            package_id=payload.package_id,
            content=payload.content,
            role=payload.role,
            trace_id=payload.trace_id,
            tags=payload.tags,
        )
        return episode.model_dump(mode="json")

    @app.delete("/memory/episodes/{episode_id}")
    def memory_delete_episode(episode_id: str, package_id: str = "mia") -> dict[str, str]:
        """Delete one episodic memory and log the deletion."""
        if not api_state.memory_store.delete_episode(episode_id, package_id):
            raise HTTPException(status_code=404, detail="episode not found")
        return {"status": "deleted", "episode_id": episode_id}

    @app.get("/memory/profile")
    def memory_profile(package_id: str = "mia") -> list[dict[str, Any]]:
        """List user profile facts for a persona package."""
        return [
            fact.model_dump(mode="json")
            for fact in api_state.memory_store.list_profile_facts(package_id)
        ]

    @app.post("/memory/profile")
    def memory_upsert_profile(payload: ProfileFactPayload) -> dict[str, Any]:
        """Create or update one profile fact."""
        fact = api_state.memory_store.upsert_profile_fact(
            package_id=payload.package_id,
            key=payload.key,
            value=payload.value,
        )
        return fact.model_dump(mode="json")

    @app.get("/memory/notes")
    def memory_notes(package_id: str = "mia", domain: str | None = None) -> list[dict[str, Any]]:
        """List domain notes for a persona package."""
        return [
            note.model_dump(mode="json")
            for note in api_state.memory_store.list_domain_notes(package_id, domain=domain)
        ]

    @app.post("/memory/notes")
    def memory_add_note(payload: DomainNotePayload) -> dict[str, Any]:
        """Append one domain note."""
        note = api_state.memory_store.add_domain_note(
            package_id=payload.package_id,
            domain=payload.domain,
            content=payload.content,
            tags=payload.tags,
        )
        return note.model_dump(mode="json")

    @app.delete("/memory/notes/{note_id}")
    def memory_delete_note(note_id: str, package_id: str = "mia") -> dict[str, str]:
        """Delete one domain note and log the deletion."""
        if not api_state.memory_store.delete_domain_note(note_id, package_id):
            raise HTTPException(status_code=404, detail="note not found")
        return {"status": "deleted", "note_id": note_id}

    @app.post("/chat")
    def chat_turn(payload: ChatPayload) -> dict[str, Any]:
        """Run one chat turn through persona, provider, and Policy Gate."""
        persona_path = api_state.persona_dir / payload.package_id
        try:
            persona = load_persona_package(persona_path)
        except PersonaPackageError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            provider = resolve_provider(payload.provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session = ChatSession(
            persona=persona,
            provider=provider,
            decision_log=api_state.decision_log,
        )
        try:
            turn = session.run_turn(payload.message)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        api_state.memory_store.add_episode(
            package_id=payload.package_id,
            role="user",
            content=payload.message,
            trace_id=turn.trace_id,
            tags=["chat"],
        )
        if not turn.blocked:
            api_state.memory_store.add_episode(
                package_id=payload.package_id,
                role="assistant",
                content=turn.response_text,
                trace_id=turn.trace_id,
                tags=["chat"],
            )

        return turn.model_dump(mode="json")

    @app.get("/aeon/status")
    def aeon_status(package_id: str = "mia") -> dict[str, Any]:
        """Return AEON runtime status for the editor."""
        try:
            runtime = api_state.get_aeon_runtime(package_id=package_id)
            payload = runtime.status()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        payload["available"] = True
        payload["version"] = aeon_version
        return payload

    @app.post("/aeon/ask")
    def aeon_ask(payload: AeonAskPayload) -> dict[str, Any]:
        """Run one request through AEON layers without GCS."""
        runtime = api_state.get_aeon_runtime(
            provider=payload.provider,
            package_id=payload.package_id,
        )
        try:
            response = runtime.ask(
                AeonRequest(message=payload.message, force_graph=payload.force_graph)
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return response.model_dump(mode="json")

    @app.post("/aeon/tick")
    def aeon_tick(package_id: str = "mia") -> dict[str, Any]:
        """Run one Active Inference heartbeat."""
        runtime = api_state.get_aeon_runtime(package_id=package_id)
        try:
            return runtime.tick()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/aeon/goals")
    def aeon_add_goal(payload: AeonGoalPayload) -> dict[str, Any]:
        """Add one user goal to the AEON goal pool."""
        runtime = api_state.get_aeon_runtime(
            provider=payload.provider,
            package_id=payload.package_id,
        )
        try:
            goal = runtime.add_goal(
                title=payload.title,
                description=payload.description,
                priority=payload.priority,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return goal.model_dump(mode="json")

    @app.post("/aeon/goals/{goal_id}/deactivate")
    def aeon_deactivate_goal(goal_id: str, package_id: str = "mia") -> dict[str, Any]:
        """Deactivate one goal in the AEON goal pool."""
        runtime = api_state.get_aeon_runtime(package_id=package_id)
        if not runtime.deactivate_goal(goal_id):
            raise HTTPException(status_code=404, detail="goal not found")
        return {"goal_id": goal_id, "active": False}

    @app.post("/aeon/consolidate")
    def aeon_consolidate(package_id: str = "mia") -> dict[str, Any]:
        """Run morning-style consolidation for goals and memory."""
        runtime = api_state.get_aeon_runtime(package_id=package_id)
        try:
            return runtime.consolidate()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/templates")
    def templates() -> list[dict[str, Any]]:
        """List built-in graph templates."""
        return [
            {
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "tags": template.tags,
                "graph_id": template.graph.graph_id,
                "node_count": template.node_count,
            }
            for template in list_templates()
        ]

    @app.get("/templates/{template_id}")
    def load_template(template_id: str) -> dict[str, Any]:
        """Load one graph template including its graph spec."""
        try:
            template = get_template(template_id)
        except TemplateNotFoundError as exc:
            raise HTTPException(status_code=404, detail="template not found") from exc
        return template.model_dump(mode="json")

    @app.post("/templates/{template_id}/instantiate")
    def create_graph_from_template(
        template_id: str,
        payload: TemplateInstantiatePayload,
    ) -> dict[str, Any]:
        """Create a graph spec from a template with optional overrides."""
        try:
            graph = instantiate_template(
                template_id,
                graph_id=payload.graph_id,
                name=payload.name,
            )
        except TemplateNotFoundError as exc:
            raise HTTPException(status_code=404, detail="template not found") from exc
        return graph.model_dump(mode="json")

    @app.get("/graphs")
    def graphs() -> list[dict[str, Any]]:
        """List saved graph files with basic metadata."""
        items: list[dict[str, Any]] = []
        for path in sorted(api_state.graph_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                spec = AgentGraphSpec.model_validate(data)
                items.append(
                    {
                        "filename": path.name,
                        "graph_id": spec.graph_id,
                        "name": spec.name,
                        "node_count": len(spec.nodes),
                    }
                )
            except (json.JSONDecodeError, ValueError):
                items.append(
                    {
                        "filename": path.name,
                        "graph_id": path.stem,
                        "name": path.stem,
                        "node_count": 0,
                    }
                )
        return items

    @app.get("/graphs/{filename}")
    def load_graph(filename: str) -> dict[str, Any]:
        """Load one saved graph spec."""
        safe_name = Path(filename).name
        path = api_state.graph_dir / safe_name
        if not path.exists():
            raise HTTPException(status_code=404, detail="graph not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            AgentGraphSpec.model_validate(data)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="invalid graph json") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return data

    @app.post("/graphs")
    def save_graph(payload: GraphSavePayload) -> dict[str, Any]:
        """Validate and persist a graph spec under `.miaos/graphs/`."""
        spec = AgentGraphSpec.model_validate(payload.graph)
        filename = payload.filename or f"{spec.graph_id}.json"
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        safe_name = Path(filename).name
        path = api_state.graph_dir / safe_name
        path.write_text(json.dumps(payload.graph, indent=2), encoding="utf-8")
        return {
            "filename": safe_name,
            "graph_id": spec.graph_id,
            "name": spec.name,
            "node_count": len(spec.nodes),
        }

    @app.post("/graphs/validate")
    def validate_graph(payload: GraphValidatePayload) -> dict[str, Any]:
        """Validate graph JSON."""
        graph = AgentGraphSpec.model_validate(payload.graph)
        return {"valid": True, "graph_id": graph.graph_id, "name": graph.name}

    @app.post("/graphs/run")
    def run_graph(payload: GraphRunPayload) -> dict[str, Any]:
        """Run graph JSON with the selected provider."""
        graph = AgentGraphSpec.model_validate(payload.graph)
        try:
            provider = resolve_provider(payload.provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        runner = GraphRunner(
            provider=provider,
            checkpoint_store=api_state.checkpoint_store,
            decision_log=api_state.decision_log,
        )
        try:
            run = runner.run(graph, input_text=payload.input_text)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        result = run.model_dump(mode="json")
        result["provider"] = provider.name
        api_state.run_events[run.run_id] = run.events
        approval = api_state.approval_queue.enqueue_from_run(
            run,
            graph=payload.graph,
            input_text=payload.input_text,
            provider=provider.name,
        )
        if approval is not None:
            result["approval_request_id"] = approval.request_id
        return result

    @app.get("/approvals")
    def approvals(status: str | None = None) -> list[dict[str, Any]]:
        """List approval queue items."""
        filter_status = ApprovalStatus(status) if status else None
        return [
            item.model_dump(mode="json")
            for item in api_state.approval_queue.list_requests(status=filter_status)
        ]

    @app.post("/approvals/{request_id}/resolve")
    def resolve_approval(request_id: str, payload: ApprovalResolvePayload) -> dict[str, Any]:
        """Approve or reject a pending approval request."""
        try:
            decision = ApprovalStatus(payload.decision)
            request = api_state.approval_queue.resolve(
                request_id,
                decision=decision,
                actor=payload.actor,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="approval request not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result: dict[str, Any] = {"request": request.model_dump(mode="json")}

        if decision == ApprovalStatus.APPROVED and request.graph:
            graph = AgentGraphSpec.model_validate(request.graph)
            try:
                provider = resolve_provider(request.provider or default_provider_name())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            runner = GraphRunner(
                provider=provider,
                checkpoint_store=api_state.checkpoint_store,
                decision_log=api_state.decision_log,
            )
            resumed = runner.resume(
                graph,
                input_text=request.input_text or "",
                outputs=dict(request.outputs),
                after_node_id=request.node_id,
                run_id=request.run_id,
                trace_id=request.trace_id,
            )
            resumed_body = resumed.model_dump(mode="json")
            resumed_body["provider"] = provider.name
            api_state.run_events[request.run_id] = (
                api_state.run_events.get(request.run_id, []) + resumed.events
            )
            result["resumed_run"] = resumed_body

        return result

    @app.websocket("/runs/{run_id}/events")
    async def run_events(websocket: WebSocket, run_id: str) -> None:
        """Send stored run events over a WebSocket and close."""
        await websocket.accept()
        events = _load_run_events(api_state, run_id)
        for event in events:
            await websocket.send_json(event.model_dump(mode="json"))
        await websocket.close()

    @app.get("/runs/{run_id}/events")
    def run_events_rest(run_id: str) -> list[dict[str, Any]]:
        """Return stored graph run events for replay."""
        events = _load_run_events(api_state, run_id)
        if not events:
            raise HTTPException(status_code=404, detail="run not found or has no events")
        return [event.model_dump(mode="json") for event in events]

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


def _load_run_events(api_state: MiaOSApiState, run_id: str) -> list[GraphEvent]:
    """Load graph events from memory or the checkpoint store."""
    return api_state.run_events.get(run_id) or api_state.checkpoint_store.list_events(run_id)


def _dump_profile_yaml(profile: dict[str, Any]) -> str:
    """Serialize profile data without adding a public YAML dependency to API callers."""
    return yaml.safe_dump(profile, sort_keys=False, allow_unicode=True)


app = create_app()
