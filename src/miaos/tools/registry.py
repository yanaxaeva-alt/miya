"""Sandbox-only tool registry with policy and audit enforcement."""

import json
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from miaos.observability import DecisionLog, DecisionLogEvent
from miaos.safety import ActionClass, ActionRequest, PolicyDecision, PolicyDecisionType, PolicyGate

type ToolOutput = dict[str, str | int | bool]
type ToolHandler = Callable[[dict[str, object]], ToolOutput]


class ToolInputError(RuntimeError):
    """Raised when a tool receives invalid or out-of-sandbox input."""


class ToolExecutionError(RuntimeError):
    """Raised when a tool cannot complete execution."""


class ToolDecisionStatus(StrEnum):
    """Runtime status for one audited tool call."""

    EXECUTED = "executed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"


class ToolSpec(BaseModel):
    """Public metadata for a sandbox-only tool."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    action_class: ActionClass
    input_schema: dict[str, object] = Field(default_factory=dict)
    sandbox_only: bool = True


class ToolCallResult(BaseModel):
    """Result of one policy-gated tool call."""

    tool_name: str
    trace_id: str
    status: ToolDecisionStatus
    policy_decision: PolicyDecision
    output: ToolOutput = Field(default_factory=dict)
    error: str | None = None


class ToolRegistry:
    """Registry for deterministic sandbox-only tools."""

    def __init__(
        self,
        *,
        sandbox_root: Path,
        decision_log: DecisionLog,
        policy_gate: PolicyGate | None = None,
    ) -> None:
        """Create a registry rooted at a sandbox directory."""
        self.sandbox_root = sandbox_root.resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.decision_log = decision_log
        self.policy_gate = policy_gate or PolicyGate()
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}
        self._register_builtin_tools()

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        """Register a sandbox-only tool implementation."""
        if spec.name in self._tools:
            msg = f"tool already registered: {spec.name}"
            raise ToolInputError(msg)
        self._tools[spec.name] = (spec, handler)

    def list_tools(self) -> list[ToolSpec]:
        """Return registered tool specifications sorted by name."""
        return [self._tools[name][0] for name in sorted(self._tools)]

    def run(
        self,
        tool_name: str,
        arguments: dict[str, object],
        *,
        actor: str = "mia.tool",
        trace_id: str | None = None,
    ) -> ToolCallResult:
        """Evaluate policy, execute an allowed tool, and audit the call."""
        if tool_name not in self._tools:
            msg = f"unknown tool: {tool_name}"
            raise ToolInputError(msg)

        spec, handler = self._tools[tool_name]
        action_class = self._action_class_for(tool_name, spec, arguments)
        resource = self._resource_for(tool_name, arguments)
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=action_class,
                actor=actor,
                resource=resource,
                description=f"tool call: {tool_name}",
                trace_id=trace_id,
            )
        )
        self.decision_log.append_policy_decision(decision)

        if decision.decision != PolicyDecisionType.ALLOW:
            status = (
                ToolDecisionStatus.APPROVAL_REQUIRED
                if decision.decision == PolicyDecisionType.REQUIRE_APPROVAL
                else ToolDecisionStatus.DENIED
            )
            result = ToolCallResult(
                tool_name=tool_name,
                trace_id=decision.trace_id,
                status=status,
                policy_decision=decision,
                error=decision.reason,
            )
            self._append_tool_event(result)
            return result

        try:
            output = handler(arguments)
        except (OSError, ValueError) as exc:
            result = ToolCallResult(
                tool_name=tool_name,
                trace_id=decision.trace_id,
                status=ToolDecisionStatus.ERROR,
                policy_decision=decision,
                error=str(exc),
            )
            self._append_tool_event(result)
            return result
        except ToolInputError as exc:
            result = ToolCallResult(
                tool_name=tool_name,
                trace_id=decision.trace_id,
                status=ToolDecisionStatus.ERROR,
                policy_decision=decision,
                error=str(exc),
            )
            self._append_tool_event(result)
            return result

        result = ToolCallResult(
            tool_name=tool_name,
            trace_id=decision.trace_id,
            status=ToolDecisionStatus.EXECUTED,
            policy_decision=decision,
            output=output,
        )
        self._append_tool_event(result)
        return result

    def _register_builtin_tools(self) -> None:
        """Register MVP sandbox tools."""
        self.register(
            ToolSpec(
                name="create_draft",
                description="Create an unpublished local draft payload.",
                action_class=ActionClass.DRAFT,
                input_schema={
                    "type": "object",
                    "required": ["title", "body"],
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                },
            ),
            self._create_draft,
        )
        self.register(
            ToolSpec(
                name="read_file_sandbox",
                description="Read a UTF-8 text file from the configured sandbox.",
                action_class=ActionClass.READ,
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                },
            ),
            self._read_file_sandbox,
        )
        self.register(
            ToolSpec(
                name="web_search_mock",
                description="Return deterministic mock web-search results without network access.",
                action_class=ActionClass.READ,
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string"}},
                },
            ),
            self._web_search_mock,
        )
        self.register(
            ToolSpec(
                name="write_file_sandbox",
                description="Write a UTF-8 text file inside the configured sandbox.",
                action_class=ActionClass.SANDBOX_WRITE,
                input_schema={
                    "type": "object",
                    "required": ["path", "content"],
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            ),
            self._write_file_sandbox,
        )

    def _read_file_sandbox(self, arguments: dict[str, object]) -> ToolOutput:
        """Read a file inside the sandbox."""
        path = self._argument_str(arguments, "path")
        resolved = self._sandbox_path(path)
        return {
            "path": str(resolved.relative_to(self.sandbox_root)),
            "content": resolved.read_text(encoding="utf-8"),
        }

    def _write_file_sandbox(self, arguments: dict[str, object]) -> ToolOutput:
        """Write a file inside the sandbox."""
        path = self._argument_str(arguments, "path")
        content = self._argument_str(arguments, "content")
        resolved = self._sandbox_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "path": str(resolved.relative_to(self.sandbox_root)),
            "bytes_written": len(content.encode("utf-8")),
        }

    @staticmethod
    def _web_search_mock(arguments: dict[str, object]) -> ToolOutput:
        """Return deterministic mock search results."""
        query = ToolRegistry._argument_str(arguments, "query")
        normalized = " ".join(query.split())
        return {
            "query": normalized,
            "result_count": 2,
            "results": (
                f"Mock result 1 for {normalized}; "
                f"Mock result 2 for {normalized}. No network access was used."
            ),
        }

    @staticmethod
    def _create_draft(arguments: dict[str, object]) -> ToolOutput:
        """Create an unpublished draft object."""
        title = ToolRegistry._argument_str(arguments, "title")
        body = ToolRegistry._argument_str(arguments, "body")
        return {
            "title": title,
            "body": body,
            "draft": f"# {title}\n\n{body}",
            "published": False,
        }

    def _sandbox_path(self, raw_path: str) -> Path:
        """Resolve a user path and require it to stay inside the sandbox."""
        requested = Path(raw_path)
        candidate = requested if requested.is_absolute() else self.sandbox_root / requested
        resolved = candidate.resolve(strict=False)
        if not self._is_inside_sandbox(resolved):
            msg = f"path escapes sandbox: {raw_path}"
            raise ToolInputError(msg)
        return resolved

    def _path_would_escape_sandbox(self, raw_path: str) -> bool:
        """Return whether a path would escape the sandbox."""
        requested = Path(raw_path)
        candidate = requested if requested.is_absolute() else self.sandbox_root / requested
        return not self._is_inside_sandbox(candidate.resolve(strict=False))

    def _is_inside_sandbox(self, path: Path) -> bool:
        """Return whether path is inside the configured sandbox root."""
        try:
            path.relative_to(self.sandbox_root)
        except ValueError:
            return False
        return True

    def _action_class_for(
        self,
        tool_name: str,
        spec: ToolSpec,
        arguments: dict[str, object],
    ) -> ActionClass:
        """Classify a tool call before policy evaluation."""
        if tool_name == "write_file_sandbox":
            path = self._argument_str(arguments, "path")
            if self._path_would_escape_sandbox(path):
                return ActionClass.WRITE_OUTSIDE_SANDBOX
        return spec.action_class

    @staticmethod
    def _resource_for(tool_name: str, arguments: dict[str, object]) -> str:
        """Return an audit resource string for a tool call."""
        raw_path = arguments.get("path")
        if isinstance(raw_path, str):
            return f"tool://{tool_name}/{raw_path}"
        return f"tool://{tool_name}"

    @staticmethod
    def _argument_str(arguments: dict[str, object], name: str) -> str:
        """Return a required string argument."""
        value = arguments.get(name)
        if not isinstance(value, str) or value == "":
            msg = f"tool argument {name!r} must be a non-empty string"
            raise ToolInputError(msg)
        return value

    def _append_tool_event(self, result: ToolCallResult) -> None:
        """Append an audited tool call event."""
        refs = {
            "tool_name": result.tool_name,
            "status": result.status.value,
            "decision": result.policy_decision.decision.value,
        }
        if result.error:
            refs["error"] = result.error
        if result.output:
            refs["output_json"] = json.dumps(
                result.output,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        self.decision_log.append(
            DecisionLogEvent(
                event_type="tool_call",
                trace_id=result.trace_id,
                summary=f"{result.tool_name} -> {result.status.value}",
                actor="tool_registry",
                refs=refs,
            )
        )
