"""Layer 5 — Fixed execution without GCS."""

from miaos.executor import CheckpointStore, GraphRunner
from miaos.models.providers import ModelProvider, resolve_provider
from miaos.observability import DecisionLog
from miaos.runtime.chat import ChatSession
from miaos.safety import PolicyGate
from miaos.templates import instantiate_template

from aeon.config import ExecutionConfig
from aeon.layers.l6_identity import IdentityCore
from aeon.types import AeonRequest, ExecutionMode


class FixedExecutionLayer:
    """Use MiaOS chat or fixed graph templates instead of generative agents."""

    def __init__(
        self,
        *,
        identity: IdentityCore,
        provider_name: str,
        decision_log: DecisionLog,
        checkpoint_store: CheckpointStore,
        config: ExecutionConfig,
        policy_gate: PolicyGate | None = None,
    ) -> None:
        self.identity = identity
        self.config = config
        self.decision_log = decision_log
        self.checkpoint_store = checkpoint_store
        self.policy_gate = policy_gate or PolicyGate()
        self.provider: ModelProvider = resolve_provider(provider_name)
        self.chat = ChatSession(
            persona=identity.persona,
            provider=self.provider,
            decision_log=decision_log,
            policy_gate=self.policy_gate,
            personality_guard=identity.guard,
        )
        self.graph_runner = GraphRunner(
            provider=self.provider,
            checkpoint_store=checkpoint_store,
            decision_log=decision_log,
            policy_gate=self.policy_gate,
        )

    def execute(self, request: AeonRequest, *, memory_context: str = "") -> tuple[str, ExecutionMode, str | None]:
        """Run the request through chat or a fixed MiaOS graph."""
        mode = self._choose_mode(request)
        if mode == ExecutionMode.CHAT:
            turn = self.chat.run_turn(request.message, extra_system_context=memory_context)
            if turn.blocked:
                return turn.response_text, ExecutionMode.CHAT, None
            return turn.response_text, ExecutionMode.CHAT, None

        enriched = self._enrich_message(request.message, memory_context=memory_context)
        template_id = (
            self.config.complex_graph_template
            if self._is_complex(enriched)
            else self.config.default_graph_template
        )
        graph = instantiate_template(template_id)
        graph_run = self.graph_runner.run(graph, input_text=enriched)
        output = graph_run.outputs.get("END") or next(iter(graph_run.outputs.values()), "")
        return output, ExecutionMode.GRAPH, template_id

    def _choose_mode(self, request: AeonRequest) -> ExecutionMode:
        if request.force_graph:
            return ExecutionMode.GRAPH
        if self._is_complex(request.message):
            return ExecutionMode.GRAPH
        if len(request.message) <= self.config.chat_max_chars:
            return ExecutionMode.CHAT
        return ExecutionMode.GRAPH

    def _is_complex(self, message: str) -> bool:
        lowered = message.casefold()
        return any(keyword in lowered for keyword in self.config.complex_keywords)

    @staticmethod
    def _enrich_message(message: str, *, memory_context: str) -> str:
        if not memory_context.strip():
            return message
        return f"{message}\n\n[AEON memory context]\n{memory_context.strip()}"
