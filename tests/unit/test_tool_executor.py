"""Tests for sandbox tool execution."""

from pathlib import Path

import pytest

from miaos.observability import DecisionLog
from miaos.safety import PolicyDecisionType
from miaos.tools.executor import SandboxToolExecutor, UnknownToolError


def test_sandbox_tool_executor_runs_web_search_mock(tmp_path: Path) -> None:
    """Registered sandbox tools return deterministic mock output."""
    executor = SandboxToolExecutor(decision_log=DecisionLog(tmp_path / "decisions.jsonl"))
    result = executor.execute(
        "web_search_mock",
        input_text="MiaOS tools",
        trace_id="trace-tool-1",
        resource="tool://Search/web_search_mock",
    )

    assert result.blocked is False
    assert result.policy_decision == PolicyDecisionType.ALLOW
    assert "[mock-search]" in result.output
    assert "MiaOS tools" in result.output


def test_sandbox_tool_executor_rejects_unknown_tool() -> None:
    """Unknown tool names fail fast."""
    executor = SandboxToolExecutor()
    with pytest.raises(UnknownToolError, match="unknown or disabled tool"):
        executor.execute(
            "publish_live",
            input_text="hello",
            trace_id="trace-tool-2",
            resource="tool://Bad/publish_live",
        )
