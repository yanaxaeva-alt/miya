"""Graph runtime event models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GraphEventType(StrEnum):
    """Graph event types emitted by the MVP executor."""

    RUN_STARTED = "run_started"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    APPROVAL_REQUIRED = "approval_required"
    RUN_COMPLETED = "run_completed"
    RUN_STOPPED = "run_stopped"


class GraphEvent(BaseModel):
    """One graph execution event."""

    run_id: str
    trace_id: str
    event_type: GraphEventType
    node_id: str | None = None
    message: str
    payload: dict[str, str | int | bool] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventStream:
    """In-memory event stream abstraction for tests and later WebSockets."""

    def __init__(self) -> None:
        """Create an empty event stream."""
        self.events: list[GraphEvent] = []

    def emit(self, event: GraphEvent) -> GraphEvent:
        """Append and return an event."""
        self.events.append(event)
        return event
