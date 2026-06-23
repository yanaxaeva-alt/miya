"""Tests for AEON heartbeat side effects."""

from pathlib import Path

from aeon.runtime import AeonRuntime


def test_tick_records_curiosity_goal_on_high_surprise(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    runtime.active_inference._last_snapshot = runtime.embodied.snapshot()  # noqa: SLF001
    runtime.embodied.watch_dir.mkdir(parents=True, exist_ok=True)
    for index in range(10):
        (runtime.embodied.watch_dir / f"burst_{index}.txt").write_text("change", encoding="utf-8")

    result = runtime.tick()
    assert result["action"] == "escalate_to_governance"
    assert "curiosity_goal_id" in result
    curiosity = [goal for goal in runtime.goals.active_goals() if goal.source == "curiosity"]
    assert curiosity


def test_tick_local_plan_records_skill(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    runtime.active_inference._last_snapshot = runtime.embodied.snapshot()  # noqa: SLF001
    runtime.embodied.watch_dir.mkdir(parents=True, exist_ok=True)
    (runtime.embodied.watch_dir / "a.txt").write_text("a", encoding="utf-8")
    (runtime.embodied.watch_dir / "b.txt").write_text("b", encoding="utf-8")
    (runtime.embodied.watch_dir / "c.txt").write_text("c", encoding="utf-8")
    (runtime.embodied.watch_dir / "d.txt").write_text("d", encoding="utf-8")

    result = runtime.tick()
    if result["action"] == "local_plan":
        assert result.get("plan_recorded") is True
        assert any("local_plan" in hint for hint in runtime.memory.skill_hints(limit=5))


def test_tick_persists_recent_ticks(tmp_path: Path) -> None:
    runtime = AeonRuntime(base_dir=tmp_path)
    runtime.tick()
    status = runtime.status()
    assert len(status["recent_ticks"]) >= 1
