"""Tests for the Policy Gate safety kernel."""

from miaos.safety import (
    DENIED_ALWAYS,
    REQUIRES_APPROVAL,
    ActionClass,
    ActionRequest,
    PolicyDecisionType,
    PolicyGate,
)


def test_denied_always_actions_are_never_allowed() -> None:
    """Every denied-always action is denied."""
    gate = PolicyGate()

    for action_class in DENIED_ALWAYS:
        decision = gate.evaluate(ActionRequest(action_class=action_class))

        assert decision.decision == PolicyDecisionType.DENY
        assert decision.capability_token is None
        assert decision.trace_id.startswith("trace_")


def test_approval_actions_never_auto_execute() -> None:
    """Approval-required actions do not receive capability tokens."""
    gate = PolicyGate()

    for action_class in REQUIRES_APPROVAL:
        decision = gate.evaluate(ActionRequest(action_class=action_class))

        assert decision.decision == PolicyDecisionType.REQUIRE_APPROVAL
        assert decision.capability_token is None


def test_allowed_action_receives_scoped_capability_token() -> None:
    """Low-risk actions receive narrow capability tokens."""
    decision = PolicyGate().evaluate(
        ActionRequest(action_class=ActionClass.READ, actor="mia.test", resource="file://sandbox/a.md")
    )

    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.capability_token is not None
    assert decision.capability_token.issued_to == "mia.test"
    assert decision.capability_token.action_class == ActionClass.READ
    assert decision.capability_token.resources["resource"] == "file://sandbox/a.md"
