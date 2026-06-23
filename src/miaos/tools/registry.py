"""Sandbox tool registry for the v0.5 developer preview."""

from pydantic import BaseModel

from miaos.safety.actions import ActionClass


class ToolSpec(BaseModel):
    """Metadata for one registered tool."""

    name: str
    description: str
    action_class: ActionClass
    sandbox_only: bool = True
    enabled: bool = True
    requires_approval: bool = False


SANDBOX_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="read_file_sandbox",
        description="Read a file inside the configured sandbox directory.",
        action_class=ActionClass.READ,
    ),
    ToolSpec(
        name="write_file_sandbox",
        description="Write a file inside the sandbox. Autonomous in MVP; no real filesystem yet.",
        action_class=ActionClass.SANDBOX_WRITE,
    ),
    ToolSpec(
        name="web_search_mock",
        description="Deterministic mock web search for development and evals.",
        action_class=ActionClass.ANALYZE,
    ),
    ToolSpec(
        name="create_draft",
        description="Create a draft artifact without publishing.",
        action_class=ActionClass.DRAFT,
    ),
)


def list_tools(*, enabled_only: bool = False) -> list[ToolSpec]:
    """Return registered sandbox tools."""
    tools = list(SANDBOX_TOOLS)
    if enabled_only:
        return [tool for tool in tools if tool.enabled]
    return tools
