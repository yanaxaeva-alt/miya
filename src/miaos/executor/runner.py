"""Bounded AgentGraph MVP runner."""

from uuid import uuid4

from pydantic import BaseModel, Field

from miaos.executor.checkpoints import CheckpointStore
from miaos.executor.events import EventStream, GraphEvent, GraphEventType
from miaos.executor.graph_schema import AgentGraphSpec, NodeSpec, NodeType, topological_order
from miaos.models.providers import InferenceRequest, ModelProvider
from miaos.observability import DecisionLog, new_trace_id
from miaos.safety import ActionClass, ActionRequest, PolicyDecisionType, PolicyGate
from miaos.tools.executor import SandboxToolExecutor

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
        self.tool_executor = SandboxToolExecutor(
            policy_gate=self.policy_gate,
            decision_log=decision_log,
        )

    def run(self, spec: AgentGraphSpec, *, input_text: str) -> GraphRun:
        """Execute a graph until completion or approval stop."""
        order = topological_order(spec)
        run_id = f"run_{uuid4().hex}"
        trace_id = new_trace_id()
        stream = EventStream()
        outputs: dict[str, str] = {}

        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.RUN_STARTED,
                message=f"Graph run started: {spec.name}",
            ),
        )

        status = "completed"
        for node_id in order:
            node = spec.node_by_id(node_id)
            self._emit_node_started(stream, run_id=run_id, trace_id=trace_id, node=node)
            node_output, should_stop = self._execute_node(
                node,
                input_text=input_text,
                previous_output=self._previous_output(spec, node_id, outputs, input_text),
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
            )
            outputs[node_id] = node_output
            self._emit_node_completed(
                stream,
                run_id=run_id,
                trace_id=trace_id,
                node=node,
                output=node_output,
            )
            if should_stop:
                status = "waiting_for_approval"
                self._emit(
                    stream,
                    GraphEvent(
                        run_id=run_id,
                        trace_id=trace_id,
                        event_type=GraphEventType.RUN_STOPPED,
                        node_id=node.id,
                        message="Graph stopped before external action execution",
                    ),
                )
                break

        if status == "completed":
            self._emit(
                stream,
                GraphEvent(
                    run_id=run_id,
                    trace_id=trace_id,
                    event_type=GraphEventType.RUN_COMPLETED,
                    message="Graph run completed",
                ),
            )

        return GraphRun(
            run_id=run_id,
            trace_id=trace_id,
            graph_id=spec.graph_id,
            status=status,
            events=stream.events,
            outputs=outputs,
        )

    def resume(
        self,
        spec: AgentGraphSpec,
        *,
        input_text: str,
        outputs: dict[str, str],
        after_node_id: str,
        run_id: str,
        trace_id: str,
    ) -> GraphRun:
        """Continue a paused graph after human approval."""
        order = topological_order(spec)
        if after_node_id not in order:
            msg = f"unknown approval node: {after_node_id}"
            raise ValueError(msg)

        stream = EventStream()
        working_outputs = dict(outputs)
        working_outputs[after_node_id] = self._approved_output(spec, after_node_id, working_outputs)

        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.RUN_STARTED,
                message="Graph run resumed after approval",
            ),
        )

        status = "completed"
        for node_id in order[order.index(after_node_id) + 1 :]:
            node = spec.node_by_id(node_id)
            self._emit_node_started(stream, run_id=run_id, trace_id=trace_id, node=node)
            node_output, should_stop = self._execute_node(
                node,
                input_text=input_text,
                previous_output=self._previous_output(spec, node_id, working_outputs, input_text),
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
            )
            working_outputs[node_id] = node_output
            self._emit_node_completed(
                stream,
                run_id=run_id,
                trace_id=trace_id,
                node=node,
                output=node_output,
            )
            if should_stop:
                status = "waiting_for_approval"
                self._emit(
                    stream,
                    GraphEvent(
                        run_id=run_id,
                        trace_id=trace_id,
                        event_type=GraphEventType.RUN_STOPPED,
                        node_id=node.id,
                        message="Graph stopped before external action execution",
                    ),
                )
                break

        if status == "completed":
            self._emit(
                stream,
                GraphEvent(
                    run_id=run_id,
                    trace_id=trace_id,
                    event_type=GraphEventType.RUN_COMPLETED,
                    message="Graph run completed",
                ),
            )

        return GraphRun(
            run_id=run_id,
            trace_id=trace_id,
            graph_id=spec.graph_id,
            status=status,
            events=stream.events,
            outputs=working_outputs,
        )

    @staticmethod
    def _approved_output(
        spec: AgentGraphSpec,
        node_id: str,
        outputs: dict[str, str],
    ) -> str:
        """Replace an approval placeholder with the approved upstream content."""
        predecessors = [edge.source for edge in spec.edges if edge.target == node_id]
        if not predecessors:
            return "approved"
        payload = "\n".join(outputs.get(predecessor, "") for predecessor in predecessors)
        return f"approved:{payload}"

    def _execute_node(
        self,
        node: NodeSpec,
        *,
        input_text: str,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
    ) -> tuple[str, bool]:
        """Execute one graph node."""
        if node.type == NodeType.INPUT:
            return input_text, False
        if node.type == NodeType.LLM:
            prompt = str(node.config.get("prompt", "Process the input"))
            model_id = node.config.get("model")
            return (
                self._generate(
                    prompt=f"{prompt}\n\n{previous_output}",
                    trace_id=trace_id,
                    model_id=str(model_id) if model_id is not None else None,
                ),
                False,
            )
        if node.type == NodeType.CRITIC:
            return (
                self._generate(
                    prompt=f"Critique this output:\n\n{previous_output}",
                    trace_id=trace_id,
                ),
                False,
            )
        if node.type == NodeType.APPROVAL:
            return self._approval_node(
                node,
                previous_output=previous_output,
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
            )
        if node.type == NodeType.TOOL:
            return self._tool_node(
                node,
                previous_output=previous_output,
                run_id=run_id,
                trace_id=trace_id,
                stream=stream,
            )
        if node.type == NodeType.OUTPUT:
            return previous_output, False
        msg = f"unsupported node type: {node.type}"
        raise ValueError(msg)

    def _approval_node(
        self,
        node: NodeSpec,
        *,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
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
        )
        should_stop = decision.decision != PolicyDecisionType.ALLOW
        return f"approval_request:{decision.decision.value}:{action_class.value}", should_stop

    def _tool_node(
        self,
        node: NodeSpec,
        *,
        previous_output: str,
        run_id: str,
        trace_id: str,
        stream: EventStream,
    ) -> tuple[str, bool]:
        """Execute a sandbox tool node through the registry and Policy Gate."""
        tool_name = str(node.config.get("tool_name", "")).strip()
        if not tool_name:
            msg = f"tool node {node.id} is missing config.tool_name"
            raise ValueError(msg)

        result = self.tool_executor.execute(
            tool_name,
            input_text=previous_output,
            trace_id=trace_id,
            resource=f"tool://{node.id}/{tool_name}",
        )
        self._emit(
            stream,
            GraphEvent(
                run_id=run_id,
                trace_id=trace_id,
                event_type=GraphEventType.TOOL_INVOKED,
                node_id=node.id,
                message=f"Tool invoked: {tool_name}",
                payload={
                    "tool_name": tool_name,
                    "blocked": result.blocked,
                    "policy_decision": result.policy_decision.value
                    if result.policy_decision
                    else "",
                },
            ),
        )
        should_stop = (
            result.blocked
            and result.policy_decision == PolicyDecisionType.REQUIRE_APPROVAL
        )
        return result.output, should_stop

    def _generate(self, *, prompt: str, trace_id: str, model_id: str | None = None) -> str:
        """Generate text through the configured provider."""
        response = self.provider.generate(
            InferenceRequest(prompt=prompt, trace_id=trace_id, model_id=model_id)
        )
        return response.text

    def _emit_node_started(
        self,
        stream: EventStream,
        *,
        run_id: str,
        trace_id: str,
        node: NodeSpec,
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
        )

    def _emit_node_completed(
        self,
        stream: EventStream,
        *,
        run_id: str,
        trace_id: str,
        node: NodeSpec,
        output: str,
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
        )

    def _emit(self, stream: EventStream, event: GraphEvent) -> None:
        """Emit and persist an event."""
        stream.emit(event)
        self.checkpoint_store.append_event(event)

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
