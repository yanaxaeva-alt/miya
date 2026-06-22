"""Deterministic sandbox tool execution for graph tool nodes."""

from pydantic import BaseModel

from miaos.observability.decision_log import DecisionLog
from miaos.safety import ActionRequest, PolicyDecisionType, PolicyGate
from miaos.tools.registry import SANDBOX_TOOLS, ToolSpec


class ToolExecutionResult(BaseModel):
    """Result of one sandbox tool invocation."""

    tool_name: str
    output: str
    blocked: bool = False
    policy_decision: PolicyDecisionType | None = None


class UnknownToolError(ValueError):
    """Raised when a graph references a tool that is not registered."""


class SandboxToolExecutor:
    """Execute registered sandbox tools through the Policy Gate."""

    def __init__(
        self,
        *,
        policy_gate: PolicyGate | None = None,
        decision_log: DecisionLog | None = None,
    ) -> None:
        """Create a sandbox tool executor."""
        self.policy_gate = policy_gate or PolicyGate()
        self.decision_log = decision_log
        self._tools = {tool.name: tool for tool in SANDBOX_TOOLS}

    def get_tool(self, tool_name: str) -> ToolSpec:
        """Return a registered tool or raise."""
        tool = self._tools.get(tool_name)
        if tool is None or not tool.enabled:
            msg = f"unknown or disabled tool: {tool_name}"
            raise UnknownToolError(msg)
        return tool

    def execute(
        self,
        tool_name: str,
        *,
        input_text: str,
        trace_id: str,
        resource: str,
    ) -> ToolExecutionResult:
        """Evaluate policy and run a deterministic mock tool."""
        tool = self.get_tool(tool_name)
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=tool.action_class,
                actor="mia.graph",
                resource=resource,
                description=input_text[:240],
                trace_id=trace_id,
            )
        )
        if self.decision_log is not None:
            self.decision_log.append_policy_decision(decision)

        if decision.decision == PolicyDecisionType.DENY:
            return ToolExecutionResult(
                tool_name=tool_name,
                output=f"tool_blocked:deny:{tool_name}",
                blocked=True,
                policy_decision=decision.decision,
            )

        if decision.decision == PolicyDecisionType.REQUIRE_APPROVAL:
            return ToolExecutionResult(
                tool_name=tool_name,
                output=f"tool_blocked:require_approval:{tool_name}",
                blocked=True,
                policy_decision=decision.decision,
            )

        return ToolExecutionResult(
            tool_name=tool_name,
            output=self._mock_execute(tool_name, input_text),
            blocked=False,
            policy_decision=decision.decision,
        )

    @staticmethod
    def _mock_execute(tool_name: str, input_text: str) -> str:
        """Return deterministic mock output for one sandbox tool."""
        query = input_text.strip() or "empty-input"
        if tool_name == "read_file_sandbox":
            return f"[sandbox-read] mock content for: {query[:120]}"
        if tool_name == "write_file_sandbox":
            return f"[sandbox-write] ok bytes={len(query.encode('utf-8'))}"
        if tool_name == "web_search_mock":
            return f"[mock-search] top result for: {query[:120]}"
        if tool_name == "create_draft":
            return f"[draft] {query[:200]}"
        msg = f"unsupported tool mock: {tool_name}"
        raise UnknownToolError(msg)
