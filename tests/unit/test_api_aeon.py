"""Tests for AEON API endpoints."""

from pathlib import Path

from fastapi.testclient import TestClient

from miaos.api import MiaOSApiState, create_app

HTTP_OK = 200


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(MiaOSApiState(tmp_path)))


def test_api_aeon_status_ask_and_tick(tmp_path: Path) -> None:
    """AEON endpoints expose status, ask, and heartbeat tick."""
    client = _client(tmp_path)
    client.post(
        "/personas",
        json={
            "name": "Mia",
            "package_id": "mia",
            "profile": {
                "identity": {"role": "AEON tester", "default_locale": "ru-RU"},
                "values": {"ranked": ["honesty", "care"]},
                "model_binding": {"provider": "mock", "model_id": "mock-aeon"},
                "autonomy_contract": {"contract_id": "aeon-contract", "autonomy_ceiling": "L3"},
            },
        },
    )

    status_response = client.get("/aeon/status", params={"package_id": "mia"})
    assert status_response.status_code == HTTP_OK
    status_body = status_response.json()
    assert status_body["available"] is True
    assert status_body["identity"] == "Mia"
    assert len(status_body["active_goals"]) >= 1

    ask_response = client.post(
        "/aeon/ask",
        json={"message": "Привет", "package_id": "mia", "provider": "mock"},
    )
    assert ask_response.status_code == HTTP_OK
    ask_body = ask_response.json()
    assert ask_body["blocked"] is False
    assert ask_body["execution_mode"] == "chat"
    assert ask_body["trace_id"]

    tick_response = client.post("/aeon/tick", params={"package_id": "mia"})
    assert tick_response.status_code == HTTP_OK
    tick_body = tick_response.json()
    assert tick_body["tick_id"]
    assert "surprise" in tick_body


def test_api_aeon_goals_and_consolidate(tmp_path: Path) -> None:
    """AEON goals persist through cached runtime and consolidate endpoint works."""
    client = _client(tmp_path)
    client.post(
        "/personas",
        json={
            "name": "Mia",
            "package_id": "mia",
            "profile": {
                "identity": {"role": "AEON tester", "default_locale": "ru-RU"},
                "values": {"ranked": ["honesty", "care"]},
                "model_binding": {"provider": "mock", "model_id": "mock-aeon"},
                "autonomy_contract": {"contract_id": "aeon-contract", "autonomy_ceiling": "L3"},
            },
        },
    )

    goal_response = client.post(
        "/aeon/goals",
        json={
            "title": "Editor polish",
            "description": "Improve AEON Studio UX",
            "priority": 0.8,
            "package_id": "mia",
            "provider": "mock",
        },
    )
    assert goal_response.status_code == HTTP_OK
    goal_body = goal_response.json()
    assert goal_body["title"] == "Editor polish"
    assert goal_body["source"] == "user"

    status_after_goal = client.get("/aeon/status", params={"package_id": "mia"}).json()
    assert any(goal["title"] == "Editor polish" for goal in status_after_goal["active_goals"])

    ask_response = client.post(
        "/aeon/ask",
        json={"message": "Привет", "package_id": "mia", "provider": "mock"},
    )
    assert ask_response.status_code == HTTP_OK

    consolidate_response = client.post("/aeon/consolidate", params={"package_id": "mia"})
    assert consolidate_response.status_code == HTTP_OK
    consolidate_body = consolidate_response.json()
    assert consolidate_body["episodes_seen"] >= 2
    assert consolidate_body["skill_recorded"] is True
    assert "summary" in consolidate_body

    deactivate_response = client.post(
        f"/aeon/goals/{goal_body['id']}/deactivate",
        params={"package_id": "mia"},
    )
    assert deactivate_response.status_code == HTTP_OK

    approval_response = client.post(
        "/aeon/ask",
        json={"message": "Please publish this draft now", "package_id": "mia", "provider": "mock"},
    )
    assert approval_response.status_code == HTTP_OK
    approval_body = approval_response.json()
    assert approval_body["blocked"] is True
    assert approval_body["metadata"].get("approval_request_id")
