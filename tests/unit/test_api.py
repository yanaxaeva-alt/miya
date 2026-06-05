"""Tests for the local FastAPI backend."""

from pathlib import Path
from threading import Thread
from time import sleep

from fastapi.testclient import TestClient

from miaos.api import MiaOSApiState, create_app
from miaos.executor import GraphEventType
from miaos.models import InferenceRequest, InferenceResponse, MockModelProvider

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
PROVIDER_DELAY_SECONDS = 0.2
LIVE_RUN_ID = "run_live_test"


class DelayedMockProvider(MockModelProvider):
    """Mock provider that pauses generation to expose live WebSocket events."""

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Delay generation and then return the deterministic mock response."""
        sleep(PROVIDER_DELAY_SECONDS)
        return super().generate(request)


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


def test_api_graph_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Graph save/load endpoints validate and persist specs safely."""
    client = _client(tmp_path)

    save_response = client.put("/graphs/example.json", json={"graph": _graph_payload()})
    list_response = client.get("/graphs")
    load_response = client.get("/graphs/example.json")

    assert save_response.status_code == HTTP_OK
    assert save_response.json()["saved"] is True
    assert list_response.json() == ["example.json"]
    assert load_response.status_code == HTTP_OK
    assert load_response.json()["graph_id"] == "api-graph"


def test_api_graph_save_rejects_path_traversal(tmp_path: Path) -> None:
    """Saved graph names cannot escape the graph directory."""
    client = _client(tmp_path)

    response = client.put("/graphs/escape..json", json={"graph": _graph_payload()})

    assert response.status_code == HTTP_BAD_REQUEST


def test_api_websocket_streams_events_while_run_is_executing(tmp_path: Path) -> None:
    """WebSocket subscribers receive events live, before the run response completes."""
    client = TestClient(create_app(MiaOSApiState(tmp_path, provider=DelayedMockProvider())))
    responses: list[dict[str, object]] = []

    def run_graph() -> None:
        response = client.post(
            "/graphs/run",
            json={
                "graph": _graph_payload(),
                "input_text": "draft a post",
                "run_id": LIVE_RUN_ID,
            },
        )
        responses.append(response.json())

    with client.websocket_connect(f"/runs/{LIVE_RUN_ID}/events") as websocket:
        thread = Thread(target=run_graph)
        thread.start()
        first_event = websocket.receive_json()
        still_running_after_first_live_event = thread.is_alive()
        received_event_types = [first_event["event_type"]]
        while received_event_types[-1] not in {
            GraphEventType.RUN_COMPLETED.value,
            GraphEventType.RUN_STOPPED.value,
        }:
            received_event_types.append(websocket.receive_json()["event_type"])
        thread.join()

    assert still_running_after_first_live_event is True
    assert received_event_types[0] == GraphEventType.RUN_STARTED.value
    assert received_event_types[-1] == GraphEventType.RUN_STOPPED.value
    assert GraphEventType.NODE_STARTED.value in received_event_types
    assert GraphEventType.APPROVAL_REQUIRED.value in received_event_types
    assert responses[0]["run_id"] == LIVE_RUN_ID


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
