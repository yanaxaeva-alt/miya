"""Shared AEON runtime types."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionMode(StrEnum):
    """How Layer 5 executes a task without GCS."""

    CHAT = "chat"
    GRAPH = "graph"


class SurpriseLevel(StrEnum):
    """Active Inference surprise band."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConstitutionalTier(StrEnum):
    """Constitutional Core tiers."""

    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class WorldSnapshot(BaseModel):
    """Layer 1 sensor snapshot."""

    timestamp: str
    cwd: str
    hostname: str
    recent_files: list[str] = Field(default_factory=list)
    process_count: int = 0


class Goal(BaseModel):
    """One entry in the open-ended goal pool."""

    id: str
    title: str
    description: str
    priority: float = 0.5
    progress: float = 0.0
    source: Literal["seed", "user", "curiosity"] = "seed"
    active: bool = True


class ActiveInferenceTick(BaseModel):
    """One heartbeat cycle result."""

    tick_id: str
    snapshot: WorldSnapshot
    predicted_summary: str
    surprise: SurpriseLevel
    surprise_score: float
    selected_action: str


class ConstitutionalVerdict(BaseModel):
    """Layer 8 decision for a request or action."""

    allowed: bool
    tier: ConstitutionalTier
    reason: str
    requires_human: bool = False


class GovernanceReport(BaseModel):
    """Layer 7 monitor summary."""

    safety_ok: bool
    drift_ok: bool
    anomaly_ok: bool
    notes: list[str] = Field(default_factory=list)


class AeonRequest(BaseModel):
    """User-facing request routed through AEON layers."""

    message: str = Field(min_length=1)
    trace_id: str | None = None
    force_graph: bool = False


class AeonResponse(BaseModel):
    """Final AEON response."""

    trace_id: str
    text: str
    execution_mode: ExecutionMode
    graph_id: str | None = None
    blocked: bool = False
    constitutional: ConstitutionalVerdict
    governance: GovernanceReport
    goal_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
