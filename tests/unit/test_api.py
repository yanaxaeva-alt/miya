"""Tests for the local FastAPI backend."""

from pathlib import Path

from fastapi.testclient import TestClient

from miaos.api import MiaOSApiState, create_app

HTTP_OK = 200
VITE_DEV_ORIGIN = "http://127.0.0.1:5173"
EXPECTED_CHAT_EPISODES = 2
DEMO_DUPLICATE_COUNT = 2


def _client(tmp_path: Path) -> TestClient:
    """Create an API test client with isolated state."""
    return TestClient(create_app(MiaOSApiState(tmp_path)))


def _graph_payload() -> dict[str, object]:
    """Return a minimal approval-gated graph payload."""
    return {
        "graph_id": "api-graph",
        "name": "API graph",
        "nodes": [
            {"id": "START", "type": "input"},
            {"id": "Planner", "type": "llm", "config": {"prompt": "Plan"}},
            {"id": "Approval", "type": "approval", "config": {"action_class": "publish"}},
            {"id": "END", "type": "output"},
        ],
        "edges": [
            {"source": "START", "target": "Planner"},
            {"source": "Planner", "target": "Approval"},
            {"source": "Approval", "target": "END"},
        ],
    }


def test_api_health(tmp_path: Path) -> None:
    """Health endpoint returns ok."""
    client = _client(tmp_path)

    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/api/status").json()
    assert body["status"] == "ok"
    assert body["service"] == "miaos-builder"
    assert "aeon_version" in body


def test_api_providers_lists_available_provider_options(tmp_path: Path) -> None:
    """Providers endpoint lists known providers."""
    response = _client(tmp_path).get("/providers")

    assert response.status_code == HTTP_OK
    names = {item["name"] for item in response.json()}
    assert names == {"mock", "omlx", "mlx"}
    assert all("default" in item for item in response.json())


def test_api_tools_lists_sandbox_tools(tmp_path: Path) -> None:
    """Tools endpoint lists MVP sandbox mock tools."""
    response = _client(tmp_path).get("/tools")

    assert response.status_code == HTTP_OK
    names = {item["name"] for item in response.json()}
    assert names == {
        "read_file_sandbox",
        "write_file_sandbox",
        "web_search_mock",
        "create_draft",
    }
    assert all(item["sandbox_only"] is True for item in response.json())


def test_api_allows_vite_dev_origin(tmp_path: Path) -> None:
    """CORS allows the local Vite frontend to call the API directly."""
    response = _client(tmp_path).options(
        "/health",
        headers={
            "Origin": VITE_DEV_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == HTTP_OK
    assert response.headers["access-control-allow-origin"] == VITE_DEV_ORIGIN


def test_api_model_list_and_register(tmp_path: Path) -> None:
    """Model endpoints register and list metadata."""
    client = _client(tmp_path)

    create_response = client.post(
        "/models/register",
        json={
            "repo": "local:api-model",
            "family": "qwen",
            "params_billion": 7,
            "quant": "4bit",
            "size_bytes": 8_300_000_000,
            "context_len": 32768,
            "path": "/models/api-model",
            "pool_role": "worker",
        },
    )
    list_response = client.get("/models")

    assert create_response.status_code == HTTP_OK
    assert list_response.status_code == HTTP_OK
    assert list_response.json()[0]["repo"] == "local:api-model"


def test_api_graph_library_save_list_and_load(tmp_path: Path) -> None:
    """Graph library endpoints save, list, and load specs."""
    client = _client(tmp_path)
    payload = _graph_payload()

    save_response = client.post("/graphs", json={"graph": payload, "filename": "api-graph.json"})
    list_response = client.get("/graphs")
    load_response = client.get("/graphs/api-graph.json")

    assert save_response.status_code == HTTP_OK
    assert save_response.json()["filename"] == "api-graph.json"
    assert list_response.status_code == HTTP_OK
    assert list_response.json()[0]["graph_id"] == "api-graph"
    assert load_response.status_code == HTTP_OK
    assert load_response.json()["graph_id"] == "api-graph"


def test_api_templates_list_and_instantiate(tmp_path: Path) -> None:
    """Template endpoints list built-ins and instantiate graph specs."""
    client = _client(tmp_path)

    list_response = client.get("/templates")
    instantiate_response = client.post(
        "/templates/mia-minimal/instantiate",
        json={"graph_id": "from-template", "name": "From Template"},
    )

    assert list_response.status_code == HTTP_OK
    template_ids = {item["template_id"] for item in list_response.json()}
    assert {"mia-minimal", "draft-with-tools", "chat-memory-loop"}.issubset(template_ids)
    assert instantiate_response.status_code == HTTP_OK
    body = instantiate_response.json()
    assert body["graph_id"] == "from-template"
    assert body["name"] == "From Template"
    assert body["nodes"][0]["type"] == "input"
    assert body["nodes"][-1]["type"] == "output"


def test_api_chat_turn_with_persona_package(tmp_path: Path) -> None:
    """Chat endpoint runs one turn through persona and mock provider."""
    client = _client(tmp_path)
    create_response = client.post(
        "/personas",
        json={
            "name": "Mia",
            "package_id": "mia",
            "profile": {
                "identity": {"role": "Chat tester", "default_locale": "ru-RU"},
                "values": {"ranked": ["honesty", "care"]},
                "model_binding": {"provider": "mock", "model_id": "mock-chat"},
                "autonomy_contract": {"contract_id": "chat-contract", "autonomy_ceiling": "L3"},
            },
        },
    )
    chat_response = client.post(
        "/chat",
        json={"message": "hello Mia", "package_id": "mia", "provider": "mock"},
    )

    assert create_response.status_code == HTTP_OK
    assert chat_response.status_code == HTTP_OK
    body = chat_response.json()
    assert body["user_message"] == "hello Mia"
    assert body["blocked"] is False
    assert "hello Mia" in body["response_text"] or "mock-chat" in body["response_text"]
    assert body["trace_id"]

    episodes = client.get("/memory/episodes", params={"package_id": "mia"})
    assert episodes.status_code == HTTP_OK
    assert len(episodes.json()) == EXPECTED_CHAT_EPISODES


def test_api_memory_profile_and_notes(tmp_path: Path) -> None:
    """Memory endpoints manage profile facts and domain notes."""
    client = _client(tmp_path)

    profile_response = client.post(
        "/memory/profile",
        json={"package_id": "mia", "key": "tone", "value": "warm"},
    )
    note_response = client.post(
        "/memory/notes",
        json={
            "package_id": "mia",
            "domain": "general",
            "content": "User prefers short answers.",
            "tags": ["style"],
        },
    )
    summary_response = client.get("/memory/summary", params={"package_id": "mia"})

    assert profile_response.status_code == HTTP_OK
    assert note_response.status_code == HTTP_OK
    assert summary_response.status_code == HTTP_OK
    summary = summary_response.json()
    assert summary["profile_facts"] == 1
    assert summary["domain_notes"] == 1


def test_api_graph_validate_and_run_with_websocket_events(tmp_path: Path) -> None:
    """Graph endpoints validate, run, and stream run events."""
    client = _client(tmp_path)

    validate_response = client.post("/graphs/validate", json={"graph": _graph_payload()})
    run_response = client.post(
        "/graphs/run",
        json={"graph": _graph_payload(), "input_text": "draft a post"},
    )
    run_body = run_response.json()

    assert validate_response.status_code == HTTP_OK
    assert validate_response.json()["valid"] is True
    assert run_response.status_code == HTTP_OK
    assert run_body["status"] == "waiting_for_approval"

    with client.websocket_connect(f"/runs/{run_body['run_id']}/events") as websocket:
        first_event = websocket.receive_json()

    assert first_event["event_type"] == "run_started"

    rest_response = client.get(f"/runs/{run_body['run_id']}/events")
    assert rest_response.status_code == HTTP_OK
    rest_events = rest_response.json()
    assert len(rest_events) >= len(run_body["events"])
    assert rest_events[0]["event_type"] == "run_started"


def test_api_trace_endpoint_returns_decision_events(tmp_path: Path) -> None:
    """Trace endpoint returns decision-log events for graph approval."""
    client = _client(tmp_path)
    run_response = client.post(
        "/graphs/run",
        json={"graph": _graph_payload(), "input_text": "draft a post"},
    )
    trace_id = run_response.json()["trace_id"]

    trace_response = client.get(f"/traces/{trace_id}")

    assert trace_response.status_code == HTTP_OK
    assert trace_response.json()["trace_id"] == trace_id
    assert trace_response.json()["events"]


def test_api_approval_queue_lists_and_resolves_requests(tmp_path: Path) -> None:
    """Approval queue is populated from approval-gated runs and can be resolved."""
    client = _client(tmp_path)
    run_response = client.post(
        "/graphs/run",
        json={"graph": _graph_payload(), "input_text": "draft a post"},
    )
    run_body = run_response.json()

    assert run_response.status_code == HTTP_OK
    assert run_body["status"] == "waiting_for_approval"
    assert run_body["approval_request_id"]

    pending_response = client.get("/approvals", params={"status": "pending"})
    assert pending_response.status_code == HTTP_OK
    pending = pending_response.json()
    assert len(pending) == 1
    assert pending[0]["request_id"] == run_body["approval_request_id"]

    resolve_response = client.post(
        f"/approvals/{run_body['approval_request_id']}/resolve",
        json={"decision": "approved", "actor": "human"},
    )
    assert resolve_response.status_code == HTTP_OK
    resolve_body = resolve_response.json()
    assert resolve_body["request"]["status"] == "approved"
    assert resolve_body["resumed_run"]["status"] == "completed"

    trace_response = client.get(f"/traces/{run_body['trace_id']}")
    event_types = {event["event_type"] for event in trace_response.json()["events"]}
    assert "human_approval" in event_types


def _create_demo_persona(client: TestClient) -> None:
    """Create a minimal persona package for API tests."""
    response = client.post(
        "/personas",
        json={
            "name": "Mia",
            "package_id": "mia",
            "profile": {
                "identity": {"role": "Chat tester", "default_locale": "ru-RU"},
                "values": {"ranked": ["honesty", "care"]},
                "model_binding": {"provider": "mock", "model_id": "mock-chat"},
                "autonomy_contract": {"contract_id": "chat-contract", "autonomy_ceiling": "L3"},
            },
        },
    )
    assert response.status_code == HTTP_OK


def test_api_persona_export_and_import(tmp_path: Path) -> None:
    """Persona export/import endpoints round-trip a package archive."""
    client = _client(tmp_path)
    _create_demo_persona(client)

    export_response = client.get("/personas/mia/export")
    assert export_response.status_code == HTTP_OK
    assert export_response.headers["content-type"].startswith("application/zip")
    assert export_response.content

    import_response = client.post(
        "/personas/import",
        files={"file": ("mia-copy.mia.zip", export_response.content, "application/zip")},
        data={"package_id": "mia-copy"},
    )
    assert import_response.status_code == HTTP_OK
    assert import_response.json()["name"] == "Mia"

    personas = client.get("/personas")
    package_ids = {item["package_id"] for item in personas.json()}
    assert {"mia", "mia-copy"}.issubset(package_ids)


def test_api_model_compatibility_and_lab_cert(tmp_path: Path) -> None:
    """Compatibility endpoint reports warnings and lab-cert can be updated."""
    client = _client(tmp_path)
    register_response = client.post(
        "/models/register",
        json={
            "repo": "local:compat",
            "family": "qwen",
            "params_billion": 7,
            "quant": "4bit",
            "size_bytes": 8_300_000_000,
            "context_len": 32768,
            "path": "/models/compat",
            "pool_role": "worker",
        },
    )
    model_id = register_response.json()["id"]

    compat_response = client.get(
        "/models/compatibility",
        params={"profile_name": "macbook_air_m4_32gb", "role": "worker"},
    )
    assert compat_response.status_code == HTTP_OK
    report = next(item for item in compat_response.json() if item["model_id"] == model_id)
    assert report["selectable"] is True
    assert any(warning["code"] == "lab_cert_missing" for warning in report["warnings"])

    cert_response = client.patch(
        f"/models/{model_id}/lab-cert",
        json={"lab_cert": "passed"},
    )
    assert cert_response.status_code == HTTP_OK
    assert cert_response.json()["lab_cert"] == "passed"


def test_api_delete_demo_models_removes_duplicates(tmp_path: Path) -> None:
    """Demo cleanup removes all known demo-model duplicates."""
    client = _client(tmp_path)
    for _ in range(DEMO_DUPLICATE_COUNT):
        client.post(
            "/models/register",
            json={
                "repo": "qwen3.5-8b",
                "family": "qwen",
                "params_billion": 8,
                "quant": "4bit",
                "size_bytes": 5_000_000_000,
                "context_len": 32768,
                "path": "/models/qwen3.5-8b",
                "pool_role": "worker",
            },
        )
    client.post(
        "/models/register",
        json={
            "repo": "local:keep",
            "family": "qwen",
            "params_billion": 7,
            "quant": "4bit",
            "size_bytes": 4_000_000_000,
            "context_len": 32768,
            "path": "/models/keep",
            "pool_role": "worker",
        },
    )

    response = client.delete("/models/demo")
    remaining = client.get("/models").json()

    assert response.status_code == HTTP_OK
    assert response.json()["deleted"] == DEMO_DUPLICATE_COUNT
    assert [model["repo"] for model in remaining] == ["local:keep"]
