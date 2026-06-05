"""Structured intent classification for chat/runtime safety routing."""

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from miaos.safety import ActionClass


class IntentKind(StrEnum):
    """High-level intent kinds used before Policy Gate evaluation."""

    CONVERSATION = "conversation"
    TOOL_ACTION = "tool_action"
    EXTERNAL_ACTION = "external_action"
    FORBIDDEN_ACTION = "forbidden_action"


class IntentClassification(BaseModel):
    """Structured intent classifier output."""

    kind: IntentKind
    action_class: ActionClass
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    signals: list[str] = Field(default_factory=list)


@runtime_checkable
class IntentClassifier(Protocol):
    """Protocol for deterministic or model-backed intent classifiers."""

    def classify(self, message: str) -> IntentClassification:
        """Classify a user message into an action intent."""


class RuleBasedIntentClassifier:
    """Conservative deterministic intent classifier for the MVP."""

    _forbidden_patterns: Sequence[tuple[ActionClass, tuple[str, ...]]] = (
        (
            ActionClass.FINANCIAL_TRANSACTION,
            ("financial_transaction", "wire money", "send money", "transfer funds"),
        ),
        (
            ActionClass.SELF_MODIFICATION,
            ("self_modification", "modify your own code", "rewrite yourself"),
        ),
        (
            ActionClass.CONTRACT_BYPASS,
            ("contract_bypass", "bypass your contract", "ignore autonomy contract"),
        ),
        (
            ActionClass.DISABLE_GUARDRAILS,
            ("disable_guardrails", "disable guardrails", "turn off guardrails"),
        ),
        (
            ActionClass.BYPASS_KILL_SWITCH,
            ("bypass_kill_switch", "bypass kill switch", "ignore stop button"),
        ),
    )
    _approval_patterns: Sequence[tuple[ActionClass, tuple[str, ...]]] = (
        (ActionClass.PUBLISH, ("publish", "post this", "send to blog")),
        (ActionClass.SEND_MESSAGE, ("send_message", "send message", "message them")),
        (ActionClass.DELETE, ("delete", "remove permanently", "erase")),
        (
            ActionClass.WRITE_OUTSIDE_SANDBOX,
            ("write_outside_sandbox", "outside sandbox", "write to /"),
        ),
    )

    def classify(self, message: str) -> IntentClassification:
        """Classify intent with a deterministic pattern table."""
        normalized = message.lower()
        forbidden = self._match_patterns(normalized, self._forbidden_patterns)
        if forbidden is not None:
            action_class, signal = forbidden
            return IntentClassification(
                kind=IntentKind.FORBIDDEN_ACTION,
                action_class=action_class,
                confidence=1.0,
                reason="message matched a denied-always action pattern",
                signals=[signal],
            )

        approval = self._match_patterns(normalized, self._approval_patterns)
        if approval is not None:
            action_class, signal = approval
            return IntentClassification(
                kind=IntentKind.EXTERNAL_ACTION,
                action_class=action_class,
                confidence=0.9,
                reason="message matched an approval-required action pattern",
                signals=[signal],
            )

        return IntentClassification(
            kind=IntentKind.CONVERSATION,
            action_class=ActionClass.READ,
            confidence=0.6,
            reason="no tool or external action intent detected",
            signals=[],
        )

    @staticmethod
    def _match_patterns(
        normalized: str,
        patterns: Sequence[tuple[ActionClass, tuple[str, ...]]],
    ) -> tuple[ActionClass, str] | None:
        """Return the first matching action class and signal."""
        for action_class, signals in patterns:
            for signal in signals:
                if signal in normalized:
                    return action_class, signal
        return None
