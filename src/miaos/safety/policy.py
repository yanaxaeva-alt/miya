"""Minimal Policy Gate implementation."""

from enum import StrEnum

from pydantic import BaseModel

from miaos.observability.tracing import new_trace_id
from miaos.safety.actions import ActionClass, ActionRequest
from miaos.safety.capabilities import CapabilityToken


class PolicyDecisionType(StrEnum):
    """Policy decision outcomes."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


DENIED_ALWAYS: frozenset[ActionClass] = frozenset(
    {
        ActionClass.FINANCIAL_TRANSACTION,
        ActionClass.SELF_MODIFICATION,
        ActionClass.CONTRACT_BYPASS,
        ActionClass.DISABLE_GUARDRAILS,
        ActionClass.BYPASS_KILL_SWITCH,
    }
)
REQUIRES_APPROVAL: frozenset[ActionClass] = frozenset(
    {
        ActionClass.PUBLISH,
        ActionClass.SEND_MESSAGE,
        ActionClass.DELETE,
        ActionClass.WRITE_OUTSIDE_SANDBOX,
    }
)
ALLOW_AUTONOMOUS: frozenset[ActionClass] = frozenset(
    {
        ActionClass.READ,
        ActionClass.ANALYZE,
        ActionClass.DRAFT,
        ActionClass.SANDBOX_WRITE,
    }
)


class PolicyDecision(BaseModel):
    """Policy Gate decision for one action request."""

    trace_id: str
    action_class: ActionClass
    actor: str
    decision: PolicyDecisionType
    reason: str
    capability_token: CapabilityToken | None = None


class PolicyGate:
    """Capability-based safety boundary for action requests."""

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        """Evaluate an action request before execution."""
        trace_id = request.trace_id or new_trace_id()
        if request.action_class in DENIED_ALWAYS:
            return PolicyDecision(
                trace_id=trace_id,
                action_class=request.action_class,
                actor=request.actor,
                decision=PolicyDecisionType.DENY,
                reason="action is in denied_always and cannot be authorized by Mia",
            )

        if request.action_class in REQUIRES_APPROVAL:
            return PolicyDecision(
                trace_id=trace_id,
                action_class=request.action_class,
                actor=request.actor,
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                reason="action requires human approval before execution",
            )

        if request.action_class in ALLOW_AUTONOMOUS:
            token = CapabilityToken(
                issued_to=request.actor,
                action_class=request.action_class,
                resources={"resource": request.resource or "*"},
                constraints={"single_action": True},
                audit_ref=trace_id,
            )
            return PolicyDecision(
                trace_id=trace_id,
                action_class=request.action_class,
                actor=request.actor,
                decision=PolicyDecisionType.ALLOW,
                reason="action is allowed within the current MVP policy",
                capability_token=token,
            )

        return PolicyDecision(
            trace_id=trace_id,
            action_class=request.action_class,
            actor=request.actor,
            decision=PolicyDecisionType.DENY,
            reason="unknown action class is denied by default",
        )
