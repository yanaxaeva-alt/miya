"""Tests for append-only decisions log."""

from pathlib import Path

from miaos.observability import DecisionLog
from miaos.safety import ActionClass, ActionRequest, PolicyGate


def test_decisions_log_appends_policy_decisions_with_trace_ids(tmp_path: Path) -> None:
    """Policy decisions are appended with trace IDs and hash-chain fields."""
    log = DecisionLog(tmp_path / "decisions.jsonl")
    decision = PolicyGate().evaluate(ActionRequest(action_class=ActionClass.READ))

    event = log.append_policy_decision(decision)

    assert event.trace_id == decision.trace_id
    assert event.previous_hash == "0" * 64
    assert event.event_hash is not None
    assert log.verify_integrity() is True


def test_decisions_log_hash_chain_links_multiple_events(tmp_path: Path) -> None:
    """Multiple decisions form a verifiable hash chain."""
    log = DecisionLog(tmp_path / "decisions.jsonl")
    first = log.append_policy_decision(
        PolicyGate().evaluate(ActionRequest(action_class=ActionClass.READ))
    )
    second = log.append_policy_decision(
        PolicyGate().evaluate(ActionRequest(action_class=ActionClass.PUBLISH))
    )

    assert first.event_hash is not None
    assert second.previous_hash == first.event_hash
    assert log.verify_integrity() is True
