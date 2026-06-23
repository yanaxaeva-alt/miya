"""Tests for sandbox tool registry."""

from miaos.safety.actions import ActionClass
from miaos.tools import list_tools


def test_list_tools_returns_four_sandbox_entries() -> None:
    """Registry exposes the four MVP mock tools."""
    tools = list_tools()
    assert len(tools) == 4
    assert {tool.name for tool in tools} == {
        "read_file_sandbox",
        "write_file_sandbox",
        "web_search_mock",
        "create_draft",
    }


def test_sandbox_tools_map_to_allow_autonomous_classes() -> None:
    """Sandbox tools only use action classes allowed autonomously in MVP."""
    allowed = {
        ActionClass.READ,
        ActionClass.ANALYZE,
        ActionClass.DRAFT,
        ActionClass.SANDBOX_WRITE,
    }
    for tool in list_tools():
        assert tool.action_class in allowed
        assert tool.sandbox_only is True
