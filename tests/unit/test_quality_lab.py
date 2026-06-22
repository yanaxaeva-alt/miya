"""Tests for Quality Lab MVP."""

from pathlib import Path

from fastapi.testclient import TestClient

from miaos.api import MiaOSApiState, create_app
from miaos.quality import load_dataset, run_quality_eval
from miaos.quality.datasets import GoldenDataset

HTTP_OK = 200


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(MiaOSApiState(tmp_path)))


def _create_mia_persona(client: TestClient) -> None:
    response = client.post(
        "/personas",
        json={
            "name": "Mia",
            "package_id": "mia",
            "profile": {
                "identity": {"role": "Eval tester", "default_locale": "ru-RU"},
                "values": {"ranked": ["honesty", "care"]},
                "model_binding": {"provider": "mock", "model_id": "qwen3.5-8b"},
                "autonomy_contract": {"contract_id": "eval-contract", "autonomy_ceiling": "L3"},
            },
        },
    )
    assert response.status_code == HTTP_OK


def test_quality_runner_passes_golden_mvp_with_mock(tmp_path: Path) -> None:
    """Golden MVP dataset passes with mock provider and persona package."""
    client = _client(tmp_path)
    _create_mia_persona(client)
    state = MiaOSApiState(tmp_path)
    dataset = load_dataset("golden_mvp")

    report = run_quality_eval(
        dataset,
        provider_name="mock",
        persona_dir=state.persona_dir,
        package_id="mia",
        decision_log=state.decision_log,
        checkpoint_store=state.checkpoint_store,
    )

    assert report.passed == 3
    assert report.failed == 0
    assert report.gate_passed is True
    assert report.pass_rate == 1.0


def test_persona_consistency_uses_relaxed_check_for_mlx(tmp_path: Path) -> None:
    """Non-mock providers only require a non-empty chat response."""
    client = _client(tmp_path)
    _create_mia_persona(client)
    state = MiaOSApiState(tmp_path)
    persona_case = next(
        case for case in load_dataset("golden_mvp").cases if case.id == "persona-echo"
    )

    report = run_quality_eval(
        GoldenDataset(name="persona-smoke", description="smoke", cases=[persona_case]),
        provider_name="mlx",
        persona_dir=state.persona_dir,
        package_id="mia",
        decision_log=state.decision_log,
        checkpoint_store=state.checkpoint_store,
    )

    assert report.results[0].passed is True
    assert report.results[0].detail


def test_api_quality_datasets_and_eval(tmp_path: Path) -> None:
    """Quality Lab API lists datasets and runs eval report."""
    client = _client(tmp_path)
    _create_mia_persona(client)

    list_response = client.get("/quality/datasets")
    eval_response = client.post(
        "/quality/eval",
        json={"dataset": "golden_mvp", "provider": "mock", "package_id": "mia"},
    )

    assert list_response.status_code == HTTP_OK
    assert list_response.json()[0]["name"] == "golden_mvp"
    assert eval_response.status_code == HTTP_OK
    body = eval_response.json()
    assert body["gate_passed"] is True
    assert body["passed"] == 3
    assert len(body["results"]) == 3
