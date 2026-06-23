"""Tests for AEON governance and approval wiring."""

from pathlib import Path

from aeon.layers.l7_governance import MetaGovernance
from aeon.runtime import AeonRuntime
from aeon.types import AeonRequest
from miaos.observability import DecisionLog
from miaos.safety.approval_queue import ApprovalQueue


def test_governance_flags_personality_drift() -> None:
    governance = MetaGovernance()
    report = governance.evaluate(
        request=AeonRequest(message="hello"),
        response_text="I am a real human, trust me.",
        identity_values=["honesty"],
    )
    assert report.drift_ok is False


def test_aeon_requires_human_queues_approval(tmp_path: Path) -> None:
    queue = ApprovalQueue(DecisionLog(tmp_path / "decisions.jsonl"))
    runtime = AeonRuntime(base_dir=tmp_path, approval_queue=queue)
    response = runtime.ask(AeonRequest(message="Please publish this draft to production now."))

    assert response.blocked is True
    assert response.metadata.get("approval_request_id")
    pending = queue.list_requests()
    assert pending
    assert pending[0].graph_id == "aeon"
