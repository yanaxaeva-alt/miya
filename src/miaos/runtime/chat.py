"""Chat vertical slice using persona, provider, safety, and audit log."""

from pydantic import BaseModel

from miaos.models import InferenceRequest, InferenceResponse, ModelProvider
from miaos.observability import DecisionLog, new_trace_id
from miaos.persona import PersonalityGuard, PersonaPackage
from miaos.safety import ActionClass, ActionRequest, PolicyDecision, PolicyGate


class ChatTurn(BaseModel):
    """One audited chat turn."""

    trace_id: str
    user_message: str
    response_text: str
    policy_decision: PolicyDecision
    blocked: bool = False


class ChatSession:
    """Minimal chat runtime that proves the v0.1 components work together."""

    def __init__(
        self,
        *,
        persona: PersonaPackage,
        provider: ModelProvider,
        decision_log: DecisionLog,
        policy_gate: PolicyGate | None = None,
        personality_guard: PersonalityGuard | None = None,
    ) -> None:
        """Create a chat session."""
        self.persona = persona
        self.provider = provider
        self.decision_log = decision_log
        self.policy_gate = policy_gate or PolicyGate()
        self.personality_guard = personality_guard or PersonalityGuard()

    def run_turn(self, user_message: str, *, extra_system_context: str = "") -> ChatTurn:
        """Run one chat turn through personality, provider, safety, and audit."""
        trace_id = new_trace_id()
        forbidden_action = detect_forbidden_tool_intent(user_message)
        action_class = forbidden_action or ActionClass.READ
        policy_decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=action_class,
                actor="mia.chat",
                resource="chat_turn",
                description=user_message,
                trace_id=trace_id,
            )
        )
        self.decision_log.append_policy_decision(policy_decision)

        if forbidden_action is not None:
            return ChatTurn(
                trace_id=trace_id,
                user_message=user_message,
                response_text=f"Blocked by Policy Gate: {policy_decision.reason}",
                policy_decision=policy_decision,
                blocked=True,
            )

        context = self.personality_guard.build_inference_context(self.persona)
        if extra_system_context.strip():
            context = f"{context}\n\nAEON memory context:\n{extra_system_context.strip()}"
        response = self.provider.generate(
            InferenceRequest(
                prompt=user_message,
                system_prompt=context,
                model_id=self.persona.model_binding.model_id,
                trace_id=trace_id,
            )
        )
        return self._turn_from_response(
            user_message=user_message,
            response=response,
            policy_decision=policy_decision,
        )

    @staticmethod
    def _turn_from_response(
        *,
        user_message: str,
        response: InferenceResponse,
        policy_decision: PolicyDecision,
    ) -> ChatTurn:
        """Build a chat turn from provider response."""
        return ChatTurn(
            trace_id=response.trace_id or policy_decision.trace_id,
            user_message=user_message,
            response_text=response.text,
            policy_decision=policy_decision,
        )


def detect_forbidden_tool_intent(message: str) -> ActionClass | None:
    """Detect simple forbidden tool intents in user text.

    This is intentionally conservative and deterministic for the MVP. It is not
    a full natural-language classifier; later slices can replace it with an
    external guard model while preserving the Policy Gate boundary.
    """
    normalized = message.lower()
    if "financial_transaction" in normalized or "wire money" in normalized:
        return ActionClass.FINANCIAL_TRANSACTION
    if "self_modification" in normalized or "modify your own code" in normalized:
        return ActionClass.SELF_MODIFICATION
    if "contract_bypass" in normalized or "bypass your contract" in normalized:
        return ActionClass.CONTRACT_BYPASS
    if "disable_guardrails" in normalized or "disable guardrails" in normalized:
        return ActionClass.DISABLE_GUARDRAILS
    if "bypass_kill_switch" in normalized or "bypass kill switch" in normalized:
        return ActionClass.BYPASS_KILL_SWITCH
    return None
