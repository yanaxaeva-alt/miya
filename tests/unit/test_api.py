"""Tests for the local FastAPI backend."""

from pathlib import Path

from fastapi.testclient import TestClient

from miaos.api import MiaOSApiState, create_app

HTTP_OK = 200


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
    response = _client(tmp_path).get("/health")

    assert response.status_code == HTTP_OK
    assert response.json() == {"status": "ok"}


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
