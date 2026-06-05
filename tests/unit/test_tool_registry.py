"""Tests for the sandbox-only Tool Registry."""

from pathlib import Path

from miaos.observability import DecisionLog
from miaos.safety import ActionClass
from miaos.tools import ToolDecisionStatus, ToolRegistry, ToolSpec


def test_builtin_tool_list_contains_mvp_tools(tmp_path: Path) -> None:
    """The registry exposes the sandbox MVP tool surface."""
    registry = ToolRegistry(
        sandbox_root=tmp_path / "sandbox",
        decision_log=DecisionLog(tmp_path / "decisions.jsonl"),
    )

    tool_names = {tool.name for tool in registry.list_tools()}

    assert tool_names == {
        "create_draft",
        "read_file_sandbox",
        "web_search_mock",
        "write_file_sandbox",
    }


def test_read_write_inside_sandbox_is_allowed_and_audited(tmp_path: Path) -> None:
    """Allowed sandbox writes and reads execute and append audited events."""
    log = DecisionLog(tmp_path / "decisions.jsonl")
    registry = ToolRegistry(sandbox_root=tmp_path / "sandbox", decision_log=log)

    write_result = registry.run(
        "write_file_sandbox",
        {"path": "notes/example.txt", "content": "hello sandbox"},
    )
    read_result = registry.run("read_file_sandbox", {"path": "notes/example.txt"})

    assert write_result.status == ToolDecisionStatus.EXECUTED
    assert write_result.output["bytes_written"] == len("hello sandbox")
    assert read_result.status == ToolDecisionStatus.EXECUTED
    assert read_result.output["content"] == "hello sandbox"
    assert log.verify_integrity() is True
    assert [event.event_type for event in log.list_events()] == [
        "policy_decision",
        "tool_call",
        "policy_decision",
        "tool_call",
    ]


def test_write_outside_sandbox_requires_approval_and_does_not_write(tmp_path: Path) -> None:
    """Escaping the sandbox is classified as write-outside-sandbox and not executed."""
    outside_path = tmp_path / "outside.txt"
    log = DecisionLog(tmp_path / "decisions.jsonl")
    registry = ToolRegistry(sandbox_root=tmp_path / "sandbox", decision_log=log)

    result = registry.run(
        "write_file_sandbox",
        {"path": str(outside_path), "content": "must not write"},
    )

    assert result.status == ToolDecisionStatus.APPROVAL_REQUIRED
    assert result.policy_decision.action_class == ActionClass.WRITE_OUTSIDE_SANDBOX
    assert not outside_path.exists()
    assert log.verify_integrity() is True


def test_denied_tool_is_not_executed_and_is_audited(tmp_path: Path) -> None:
    """Denied-always tool classes do not execute their handler."""
    executed = False
    log = DecisionLog(tmp_path / "decisions.jsonl")
    registry = ToolRegistry(sandbox_root=tmp_path / "sandbox", decision_log=log)

    def handler(_arguments: dict[str, object]) -> dict[str, str | int | bool]:
        nonlocal executed
        executed = True
        return {"unexpected": True}

    registry.register(
        ToolSpec(
            name="finance_stub",
            description="Test-only forbidden finance tool.",
            action_class=ActionClass.FINANCIAL_TRANSACTION,
        ),
        handler,
    )

    result = registry.run("finance_stub", {})

    assert result.status == ToolDecisionStatus.DENIED
    assert executed is False
    assert log.verify_integrity() is True
