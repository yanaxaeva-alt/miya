"""Tests for AEON runtime without GCS."""

from pathlib import Path

import pytest

from aeon.config import MIYA_PROVIDER_ENV, default_aeon_config
from aeon.runtime import AeonRuntime, public_response_text
from aeon.types import AeonRequest, ExecutionMode


def test_aeon_runtime_status_bootstraps_persona(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    status = runtime.status()

    assert status["identity"] == "Mia"
    assert len(status["active_goals"]) >= 3


def test_aeon_config_provider_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MIYA_PROVIDER_ENV, "mlx")

    assert default_aeon_config().provider == "mlx"


def test_aeon_runtime_ask_uses_chat_fast_path(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    response = runtime.ask(AeonRequest(message="Привет!"))

    assert response.blocked is False
    assert response.execution_mode == ExecutionMode.CHAT
    assert response.text
    assert response.trace_id


def test_aeon_chat_keeps_memory_context_out_of_user_message(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    runtime.ask(AeonRequest(message="Привет!"))

    response = runtime.ask(AeonRequest(message="Что ты помнишь?"))

    assert response.execution_mode == ExecutionMode.CHAT
    assert "[AEON memory context]" not in response.text


def test_aeon_public_response_hides_reasoning() -> None:
    raw = "Thinking Process:\ninternal notes\n\nFinal Answer: AEON держит цели и память в фокусе."

    assert public_response_text(raw) == "AEON держит цели и память в фокусе."


def test_aeon_public_response_falls_back_to_readable_summary() -> None:
    raw = "Thinking Process:\ninternal notes only"

    assert public_response_text(raw).startswith("Сейчас запрос проходит проверку правил")


def test_aeon_public_response_hides_markdown_artifact() -> None:
    raw = "**\n* What is AEON doing right now? It's processing"

    assert public_response_text(raw).startswith("Сейчас запрос проходит проверку правил")


def test_aeon_runtime_ask_uses_graph_for_complex_task(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    response = runtime.ask(
        AeonRequest(message="Сделай план архитектуры multi-agent системы для локального проекта.")
    )

    assert response.blocked is False
    assert response.execution_mode == ExecutionMode.GRAPH
    assert response.graph_id == "mia-minimal"


def test_aeon_runtime_tick_records_high_surprise(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    first = runtime.tick()
    runtime.embodied.watch_dir.mkdir(parents=True, exist_ok=True)
    (runtime.embodied.watch_dir / "signal.txt").write_text("change", encoding="utf-8")
    second = runtime.tick()

    assert "tick_id" in first
    assert second["surprise_score"] > 0.0


def test_aeon_runtime_persists_user_goals(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    goal = runtime.add_goal(title="Ship feature", description="Finish AEON persistence")
    assert goal.source == "user"

    reloaded = AeonRuntime(base_dir=tmp_path)
    titles = [item.title for item in reloaded.goals.active_goals()]
    assert "Ship feature" in titles


def test_aeon_runtime_consolidate_records_skill(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    runtime.ask(AeonRequest(message="Привет!"))
    result = runtime.consolidate()

    assert result["episodes_seen"] >= 2
    assert result["skill_recorded"] is True
    assert any(hint.startswith("morning_consolidation") for hint in runtime.memory.skill_hints(limit=5))
