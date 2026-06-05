"""Chat vertical slice using persona, provider, safety, and audit log."""

from pydantic import BaseModel

from miaos.models import InferenceRequest, InferenceResponse, ModelProvider
from miaos.observability import DecisionLog, new_trace_id
from miaos.persona import PersonalityGuard, PersonaPackage
from miaos.runtime.intent import (
    IntentClassification,
    IntentClassifier,
    IntentKind,
    RuleBasedIntentClassifier,
)
from miaos.safety import ActionClass, ActionRequest, PolicyDecision, PolicyDecisionType, PolicyGate


class ChatTurn(BaseModel):
    """One audited chat turn."""

    trace_id: str
    user_message: str
    response_text: str
    policy_decision: PolicyDecision
    intent: IntentClassification
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
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        """Create a chat session."""
        self.persona = persona
        self.provider = provider
        self.decision_log = decision_log
        self.policy_gate = policy_gate or PolicyGate()
        self.personality_guard = personality_guard or PersonalityGuard()
        self.intent_classifier = intent_classifier or RuleBasedIntentClassifier()

    def run_turn(self, user_message: str) -> ChatTurn:
        """Run one chat turn through personality, provider, safety, and audit."""
        trace_id = new_trace_id()
        intent = self.intent_classifier.classify(user_message)
        policy_decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=intent.action_class,
                actor="mia.chat",
                resource="chat_turn",
                description=user_message,
                trace_id=trace_id,
            )
        )
        self.decision_log.append_policy_decision(policy_decision)

        if policy_decision.decision != PolicyDecisionType.ALLOW:
            return ChatTurn(
                trace_id=trace_id,
                user_message=user_message,
                response_text=f"Blocked by Policy Gate: {policy_decision.reason}",
                policy_decision=policy_decision,
                intent=intent,
                blocked=True,
            )

        context = self.personality_guard.build_inference_context(self.persona)
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
            intent=intent,
        )

    @staticmethod
    def _turn_from_response(
        *,
        user_message: str,
        response: InferenceResponse,
        policy_decision: PolicyDecision,
        intent: IntentClassification,
    ) -> ChatTurn:
        """Build a chat turn from provider response."""
        return ChatTurn(
            trace_id=response.trace_id or policy_decision.trace_id,
            user_message=user_message,
            response_text=response.text,
            policy_decision=policy_decision,
            intent=intent,
        )


def detect_forbidden_tool_intent(message: str) -> ActionClass | None:
    """Return denied-always action intent for backward-compatible callers."""
    intent = RuleBasedIntentClassifier().classify(message)
    if intent.kind == IntentKind.FORBIDDEN_ACTION:
        return intent.action_class
    return None
