"""Append-only decisions log with a SHA-256 hash chain."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from miaos.safety.policy import PolicyDecision

ZERO_HASH = "0" * 64


class DecisionLogEvent(BaseModel):
    """Serializable audit event for `decisions.jsonl`."""

    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_type: str
    trace_id: str
    summary: str
    actor: str
    refs: dict[str, str] = Field(default_factory=dict)
    previous_hash: str = ZERO_HASH
    event_hash: str | None = None


class DecisionLog:
    """Append-only decisions log."""

    def __init__(self, path: Path) -> None:
        """Create a decision log at the provided path."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: DecisionLogEvent) -> DecisionLogEvent:
        """Append an event and return it with hash-chain fields populated."""
        previous_hash = self._last_hash()
        event.previous_hash = previous_hash
        event.event_hash = self._hash_event(event, previous_hash=previous_hash)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{event.model_dump_json()}\n")
        return event

    def append_policy_decision(self, decision: PolicyDecision) -> DecisionLogEvent:
        """Append a policy decision event."""
        token_ref = decision.capability_token.token_id if decision.capability_token else ""
        return self.append(
            DecisionLogEvent(
                event_type="policy_decision",
                trace_id=decision.trace_id,
                summary=f"{decision.action_class.value} -> {decision.decision.value}",
                actor="policy_gate",
                refs={"capability_token": token_ref} if token_ref else {},
            )
        )

    def verify_integrity(self) -> bool:
        """Verify the log hash chain."""
        previous_hash = ZERO_HASH
        for event in self.list_events():
            expected_hash = self._hash_event(event, previous_hash=previous_hash)
            if event.previous_hash != previous_hash or event.event_hash != expected_hash:
                return False
            previous_hash = event.event_hash
        return True

    def _last_hash(self) -> str:
        """Return the current hash-chain tip."""
        events = self.list_events()
        if not events:
            return ZERO_HASH
        return events[-1].event_hash or ZERO_HASH

    def list_events(self) -> list[DecisionLogEvent]:
        """Read all events from the log."""
        if not self.path.exists():
            return []
        return [
            DecisionLogEvent.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _hash_event(event: DecisionLogEvent, *, previous_hash: str) -> str:
        """Hash an event using its previous hash and stable JSON body."""
        payload = event.model_dump(mode="json", exclude={"event_hash"})
        payload["previous_hash"] = previous_hash
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(f"{previous_hash}{body}".encode()).hexdigest()


def event_to_dict(event: DecisionLogEvent) -> dict[str, Any]:
    """Return a JSON-compatible event mapping."""
    return event.model_dump(mode="json")
