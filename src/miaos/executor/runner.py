"""Bounded AgentGraph MVP runner."""

from collections.abc import Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from miaos.executor.checkpoints import CheckpointStore
from miaos.executor.events import EventStream, GraphEvent, GraphEventType
from miaos.executor.graph_schema import AgentGraphSpec, NodeSpec, NodeType, topological_order
from miaos.models.providers import InferenceRequest, ModelProvider
from miaos.observability import DecisionLog, new_trace_id
from miaos.safety import ActionClass, ActionRequest, PolicyDecisionType, PolicyGate

EVENT_OUTPUT_PREVIEW_CHARS = 120


class GraphRun(BaseModel):
    """Completed or stopped graph run."""

    run_id: str
    trace_id: str
    graph_id: str
    status: str
    events: list[GraphEvent] = Field(default_factory=list)
    outputs: dict[str, str] = Field(default_factory=dict)


class GraphRunner:
    """Execute validated AgentGraph DAGs with a model provider."""

    def __init__(
        self,
        *,
        provider: ModelProvider,
        checkpoint_store: CheckpointStore,
        decision_log: DecisionLog,
        policy_gate: PolicyGate | None = None,
    ) -> None:
        """Create a graph runner."""
        self.provider = provider
        self.checkpoint_store = checkpoint_store
        self.decision_log = decision_log
        self.policy_gate = policy_gate or PolicyGate()

    def run(
        self,
        spec: AgentGraphSpec,
        *,
        input_text: str,
        run_id: str | None = None,
        trace_id: str | None = None,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> GraphRun:
        """Execute a graph until completion or approval stop."""
        order = topological_order(spec)
        resolved_run_id = run_id or f"run_{uuid4().hex}"
        resolved_trace_id = trace_id or new_trace_id()
        stream = EventStream()
        outputs: dict[str, str] = {}

        self._emit(
            stream,
            GraphEvent(
                run_id=resolved_run_id,
                trace_id=resolved_trace_id,
                event_type=GraphEventType.RUN_STARTED,
                message=f"Graph run started: {spec.name}",
            ),
            event_sink=event_sink,
        )

        status = "completed"
        for node_id in order:
            node = spec.node_by_id(node_id)
            self._emit_node_started(
                stream,
                run_id=resolved_run_id,
                trace_id=resolved_trace_id,
                node=node,
                event_sink=event_sink,
            )
            node_output, should_stop = self._execute_node(
                node,
                input_text=input_text,
                previous_output=self._previous_output(spec, node_id, outputs, input_text),
                run_id=resolved_run_id,
                trace_id=resolved_trace_id,
                stream=stream,
                event_sink=event_sink,
            )
            outputs[node_id] = node_output
            self._emit_node_completed(
                stream,
                run_id=resolved_run_id,
                trace_id=resolved_trace_id,
                node=node,
                output=node_output,
                event_sink=event_sink,
            )
            if should_stop:
                status = "waiting_for_approval"
                self._emit(
                    stream,
                    GraphEvent(
                        run_id=resolved_run_id,
                        trace_id=resolved_trace_id,
                        event_type=GraphEventType.RUN_STOPPED,
                        node_id=node.id,
                        message="Graph stopped before external action execution",
                    ),
                    event_sink=event_sink,
                )
                break

        if status == "completed":
            self._emit(
                stream,
                GraphEvent(
                        run_id=resolved_run_id,
                        trace_id=resolved_trace_id,
                    event_type=GraphEventType.RUN_COMPLETED,
                    message="Graph run completed",
                ),
                    event_sink=event_sink,
            )

        return GraphRun(
            run_id=resolved_run_id,
            trace_id=resolved_trace_id,
            graph_id=spec.graph_id,
            status=status,
            events=stream.events,
            outputs=outputs,
        )

    def _execute_node(
        self,
        node: NodeSpec,
        *,
        input_text: str,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> tuple[str, bool]:
        """Execute one graph node."""
        if node.type == NodeType.INPUT:
            return input_text, False
        if node.type == NodeType.LLM:
            prompt = str(node.config.get("prompt", "Process the input"))
            return self._generate(prompt=f"{prompt}\n\n{previous_output}", trace_id=trace_id), False
        if node.type == NodeType.CRITIC:
            return (
                self._generate(
                    prompt=f"Critique this output:\n\n{previous_output}",
                    trace_id=trace_id,
                ),
                False,
            )
        if node.type == NodeType.TOOL:
            return self._tool_node(
                node,
                previous_output=previous_output,
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
                event_sink=event_sink,
            )
        if node.type == NodeType.MEMORY:
            return f"memory_context:mock:{previous_output[:EVENT_OUTPUT_PREVIEW_CHARS]}", False
        if node.type == NodeType.APPROVAL:
            return self._approval_node(
                node,
                previous_output=previous_output,
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
                event_sink=event_sink,
            )
        if node.type == NodeType.OUTPUT:
            return previous_output, False
        msg = f"unsupported node type: {node.type}"
        raise ValueError(msg)

    def _tool_node(
        self,
        node: NodeSpec,
        *,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> tuple[str, bool]:
        """Mock-run a tool node through Policy Gate without external side effects."""
        raw_action_class = str(node.config.get("action_class", ActionClass.READ.value))
        action_class = ActionClass(raw_action_class)
        tool_name = str(node.config.get("tool_name", "mock_tool"))
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=action_class,
                actor="mia.graph.tool",
                resource=node.id,
                description=f"{tool_name}: {previous_output}",
                trace_id=trace_id,
            )
        )
        self.decision_log.append_policy_decision(decision)
        if decision.decision != PolicyDecisionType.ALLOW:
            self._emit(
                stream,
                GraphEvent(
                    run_id=run_id,
                    trace_id=trace_id,
                    event_type=GraphEventType.APPROVAL_REQUIRED,
                    node_id=node.id,
                    message=f"Tool policy decision: {decision.decision.value}",
                    payload={
                        "decision": decision.decision.value,
                        "action_class": action_class.value,
                        "tool_name": tool_name,
                    },
                ),
                event_sink=event_sink,
            )
            return f"tool_blocked:{decision.decision.value}:{action_class.value}", True
        return f"tool_mock:{tool_name}:{action_class.value}", False

    def _approval_node(
        self,
        node: NodeSpec,
        *,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> tuple[str, bool]:
        """Create an approval request instead of executing an external action."""
        raw_action_class = str(node.config.get("action_class", ActionClass.PUBLISH.value))
        action_class = ActionClass(raw_action_class)
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=action_class,
                actor="mia.graph",
                resource=node.id,
                description=previous_output,
                trace_id=trace_id,
            )
        )
        self.decision_log.append_policy_decision(decision)
        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.APPROVAL_REQUIRED,
                node_id=node.id,
                message=f"Approval decision: {decision.decision.value}",
                payload={"decision": decision.decision.value, "action_class": action_class.value},
            ),
            event_sink=event_sink,
        )
        should_stop = decision.decision != PolicyDecisionType.ALLOW
        return f"approval_request:{decision.decision.value}:{action_class.value}", should_stop

    def _generate(self, *, prompt: str, trace_id: str) -> str:
        """Generate text through the configured provider."""
        response = self.provider.generate(InferenceRequest(prompt=prompt, trace_id=trace_id))
        return response.text

    def _emit_node_started(
        self,
        stream: EventStream,
        *,
        run_id: str,
        trace_id: str,
        node: NodeSpec,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> None:
        """Emit a node-started event."""
        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.NODE_STARTED,
                node_id=node.id,
                message=f"Node started: {node.id}",
            ),
            event_sink=event_sink,
        )

    def _emit_node_completed(
        self,
        stream: EventStream,
        *,
        run_id: str,
        trace_id: str,
        node: NodeSpec,
        output: str,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> None:
        """Emit a node-completed event."""
        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.NODE_COMPLETED,
                node_id=node.id,
                message=f"Node completed: {node.id}",
                payload={"output": output[:EVENT_OUTPUT_PREVIEW_CHARS]},
            ),
            event_sink=event_sink,
        )

    def _emit(
        self,
        stream: EventStream,
        event: GraphEvent,
        *,
        event_sink: Callable[[GraphEvent], None] | None = None,
    ) -> None:
        """Emit and persist an event."""
        stream.emit(event)
        self.checkpoint_store.append_event(event)
        if event_sink is not None:
            event_sink(event)

    @staticmethod
    def _previous_output(
        spec: AgentGraphSpec,
        node_id: str,
        outputs: dict[str, str],
        input_text: str,
    ) -> str:
        """Return the joined outputs from predecessor nodes."""
        predecessors = [edge.source for edge in spec.edges if edge.target == node_id]
        if not predecessors:
            return input_text
        return "\n".join(outputs.get(predecessor, "") for predecessor in predecessors)
