"""In-memory approval queue for graph runs that stop at approval nodes."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from typing import Any

from pydantic import BaseModel, Field

from miaos.executor.events import GraphEventType
from miaos.executor.runner import GraphRun
from miaos.observability import DecisionLog, DecisionLogEvent


class ApprovalStatus(StrEnum):
    """Lifecycle status for a queued approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    """Human approval item surfaced to the editor queue."""

    request_id: str
    run_id: str
    trace_id: str
    graph_id: str
    node_id: str
    action_class: str
    summary: str
    graph: dict[str, Any] | None = None
    input_text: str | None = None
    provider: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class ApprovalQueue:
    """Store pending and resolved approval requests for the local API."""

    def __init__(self, decision_log: DecisionLog) -> None:
        """Create a queue backed by the shared decision log."""
        self.decision_log = decision_log
        self._items: dict[str, ApprovalRequest] = {}

    def enqueue_from_run(
        self,
        run: GraphRun,
        *,
        graph: dict[str, Any] | None = None,
        input_text: str | None = None,
        provider: str | None = None,
    ) -> ApprovalRequest | None:
        """Create a pending request when a graph stops before external action."""
        if run.status != "waiting_for_approval":
            return None

        approval_event = next(
            (
                event
                for event in run.events
                if event.event_type == GraphEventType.APPROVAL_REQUIRED
            ),
            None,
        )
        if approval_event is None or not approval_event.node_id:
            return None

        action_class = str(approval_event.payload.get("action_class", "publish"))
        output_preview = run.outputs.get(approval_event.node_id, approval_event.message)
        request = ApprovalRequest(
            request_id=f"appr_{uuid4().hex}",
            run_id=run.run_id,
            trace_id=run.trace_id,
            graph_id=run.graph_id,
            node_id=approval_event.node_id,
            action_class=action_class,
            summary=f"{action_class}: {output_preview[:160]}",
            graph=graph,
            input_text=input_text,
            provider=provider,
            outputs=dict(run.outputs),
        )
        self._items[request.request_id] = request
        return request

    def enqueue_aeon_side_effect(
        self,
        *,
        trace_id: str,
        message: str,
        summary: str,
        action_class: str = "aeon_side_effect",
        provider: str | None = None,
    ) -> ApprovalRequest:
        """Queue a constitutional Tier 2 checkpoint for AEON requests."""
        request = ApprovalRequest(
            request_id=f"appr_{uuid4().hex}",
            run_id=f"aeon_{trace_id}",
            trace_id=trace_id,
            graph_id="aeon",
            node_id="constitutional_tier_2",
            action_class=action_class,
            summary=summary,
            input_text=message,
            provider=provider,
        )
        self._items[request.request_id] = request
        self.decision_log.append(
            DecisionLogEvent(
                event_type="approval_required",
                trace_id=trace_id,
                summary=summary,
                actor="aeon",
                refs={"request_id": request.request_id, "graph_id": "aeon"},
            )
        )
        return request

    def list_requests(self, *, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        """Return queue items, optionally filtered by status."""
        items = list(self._items.values())
        if status is None:
            return sorted(items, key=lambda item: item.created_at, reverse=True)
        return sorted(
            [item for item in items if item.status == status],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get(self, request_id: str) -> ApprovalRequest | None:
        """Return one queue item if it exists."""
        return self._items.get(request_id)

    def resolve(
        self,
        request_id: str,
        *,
        decision: ApprovalStatus,
        actor: str = "human",
    ) -> ApprovalRequest:
        """Resolve a pending request and append a human decision to the audit log."""
        if decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            msg = f"unsupported approval decision: {decision}"
            raise ValueError(msg)

        request = self._items.get(request_id)
        if request is None:
            msg = f"approval request not found: {request_id}"
            raise KeyError(msg)
        if request.status != ApprovalStatus.PENDING:
            msg = f"approval request already resolved: {request_id}"
            raise ValueError(msg)

        request.status = decision
        request.resolved_at = datetime.now(UTC)
        request.resolved_by = actor
        self.decision_log.append(
            DecisionLogEvent(
                event_type="human_approval",
                trace_id=request.trace_id,
                summary=f"{request.action_class} -> {decision.value} by {actor}",
                actor=actor,
                refs={
                    "request_id": request.request_id,
                    "run_id": request.run_id,
                    "node_id": request.node_id,
                },
            )
        )
        return request
