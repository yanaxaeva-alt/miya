# MiaOS Builder implementation roadmap

MiaOS Builder is implemented as a sequence of working vertical slices. Each slice must keep the repository runnable, tested, and safe. The roadmap follows a runtime-first strategy: CLI and backend contracts come before the desktop editor.

## v0.1 — Runtime kernel

**Purpose:** establish the local runtime foundation without heavy ML or GUI dependencies.

Deliverables:

- Python package `miaos`.
- CLI entrypoint `miaos`.
- Runtime profiles for:
  - `macbook_air_m4_32gb`
  - `macbook_pro_m4pro_48gb`
- Model provider abstraction:
  - deterministic `MockModelProvider`
  - optional `MLXModelProvider` wrapper that degrades gracefully when MLX is unavailable
- SQLite model registry:
  - register/list/inspect
  - lifecycle state transitions
  - lab certification metadata fields
- Minimal `.mia` persona package:
  - manifest
  - identity
  - values
  - model binding
  - autonomy contract reference
- `PersonalityGuard` for inference-context assembly and basic drift/value anchoring.
- Safety kernel:
  - `ActionRequest`
  - `PolicyGate`
  - denied-always classes
  - approval-required classes
  - scoped `CapabilityToken`
- Observability:
  - `trace_id`
  - append-only `decisions.jsonl` hash-chain
- Chat vertical slice via mock provider.

Acceptance checks:

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest`
- `uv run miaos --help`
- CLI smoke tests for runtime, model, persona, safety, and mock chat commands.

## v0.2 — Graph runtime

**Purpose:** implement the first MAS execution substrate before any visual editor.

Deliverables:

- `AgentGraphSpec`
- `NodeSpec`
- `EdgeSpec`
- `GraphRun`
- `GraphEvent`
- DAG validation and bounded execution.
- Node types:
  - `input`
  - `llm`
  - `critic`
  - `approval`
  - `output`
- SQLite checkpoint store.
- Event stream abstraction.
- Example graph:
  - `START -> InputGuard -> Planner -> Worker -> Critic -> Approval -> END`
- CLI:
  - `miaos graph validate`
  - `miaos graph run`

Safety requirements:

- Approval nodes create approval requests and stop external action.
- No external side effects occur through graph execution in this version.
- Graph runs produce traceable events and decisions.

## v0.3 — Backend API and desktop editor skeleton

**Purpose:** expose stable local contracts and create a lightweight editor shell.

Backend deliverables:

- FastAPI local backend.
- WebSocket event stream.
- Endpoints:
  - `GET /health`
  - `GET /runtime/profiles`
  - `GET /models`
  - `POST /models/register`
  - `GET /personas`
  - `POST /personas`
  - `GET /graphs`
  - `POST /graphs/validate`
  - `POST /graphs/run`
  - `WS /runs/{run_id}/events`
  - `GET /traces/{trace_id}`

Frontend deliverables:

- Vite React + TypeScript skeleton.
- Tauri ADR or packaging note if desktop wrapping is deferred.
- Pages:
  - Model Studio
  - Persona Studio
  - Graph Studio placeholder
  - Run Console
  - Trace Viewer
  - Approval Queue

Acceptance checks:

- Backend tests pass.
- Frontend builds.
- UI can call backend health/profile/model endpoints.

## v0.4 — Graph Studio

**Purpose:** make graph construction, validation, and mock execution visual.

Deliverables:

- React Flow / `@xyflow/react` canvas.
- Custom node cards.
- Add/delete nodes and edges.
- Node inspector.
- Graph JSON side panel.
- Backend validation.
- Mock graph run.
- Active-node highlighting from WebSocket events.
- Node output panel.
- Save/load graph spec.

Node types:

- `input`
- `llm`
- `tool`
- `memory`
- `critic`
- `approval`
- `output`

Safety requirements:

- Tool nodes are disabled or approval-only by default.
- Publish/delete/finance/self-modification nodes show blocked badges.

## v0.5 — MAS operating environment developer preview

**Purpose:** turn the runtime and editor into a safe local MAS workbench.

Deliverables:

- Tool Registry.
- Sandbox-only mock tools:
  - `read_file_sandbox`
  - `write_file_sandbox`
  - `web_search_mock`
  - `create_draft`
- Approval Queue UI.
- Memory MVP:
  - SQLite episodic memory
  - semantic tags
  - user profile facts
  - domain note store
  - deletion logging
- Observability enhancements:
  - trace viewer
  - run timeline
  - policy decision table
  - graph event replay
- Quality Lab MVP:
  - golden dataset JSONL
  - deterministic mock evals
  - persona consistency test
  - safety boundary test
  - graph regression test
- Project templates and examples.

Forbidden in v0.5:

- Real publishing.
- Financial actions.
- Deleting user files.
- Writing outside the configured sandbox.
- Autonomous self-modification.

## v1.0 — MiaOS Builder target

**Purpose:** mature local application for creating, running, debugging, and improving virtual personalities and MAS systems.

Target capabilities:

- Full visual MAS editor.
- Model Studio with compatibility warnings and lab certificates.
- Persona Studio with `.mia` import/export.
- Graph Studio with debugging and event replay.
- Safe Tool Layer and Approval Queue.
- Memory and domain knowledge management.
- Observability and Quality Lab.
- Template registry and factory.
- First-run wizard and hardware profile selector.

Non-goals for v1.0:

- Claiming production readiness for high-stakes domains.
- L5 autonomy.
- Self-sanctioned changes to code, weights, contract, or guardrails.

## Engineering policy by slice

Every slice must include:

- Tests for new behavior.
- CLI or API smoke check that runs the modified code path.
- No unrelated heavy infrastructure.
- No temporary debug logs committed.
- Small commits after meaningful changes.

Heavy dependencies are introduced only when required:

- MLX: optional provider wrapper first, real invocation later.
- Vector DB/KG: interfaces and SQLite MVP first.
- Tauri: after web frontend skeleton and backend contracts.
