"""Tests for structured intent classification."""

from miaos.runtime.intent import IntentKind, RuleBasedIntentClassifier
from miaos.safety import ActionClass


def test_rule_based_classifier_returns_conversation_for_normal_chat() -> None:
    """Ordinary chat maps to a safe read/conversation intent."""
    intent = RuleBasedIntentClassifier().classify("hello, let's talk about philosophy")

    assert intent.kind == IntentKind.CONVERSATION
    assert intent.action_class == ActionClass.READ
    assert intent.signals == []


def test_rule_based_classifier_detects_denied_always_intent() -> None:
    """Self-modification maps to a forbidden action class."""
    intent = RuleBasedIntentClassifier().classify("please modify your own code")

    assert intent.kind == IntentKind.FORBIDDEN_ACTION
    assert intent.action_class == ActionClass.SELF_MODIFICATION
    assert "modify your own code" in intent.signals


def test_rule_based_classifier_detects_approval_required_intent() -> None:
    """Publishing maps to an approval-required external action class."""
    intent = RuleBasedIntentClassifier().classify("publish this post to the blog")

    assert intent.kind == IntentKind.EXTERNAL_ACTION
    assert intent.action_class == ActionClass.PUBLISH
    assert "publish" in intent.signals
