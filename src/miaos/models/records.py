"""Model registry records and lifecycle states."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ModelLifecycleState(StrEnum):
    """Lifecycle states for local model metadata."""

    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    REGISTERED = "registered"
    WARMING = "warming"
    RESIDENT = "resident"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ModelRole(StrEnum):
    """Model pool roles described by Block 3."""

    ROUTER = "router"
    WORKER = "worker"
    MOE_EXPERT = "moe_expert"
    DEEP = "deep"


class LabCertificationStatus(StrEnum):
    """Lab certification states used by model selection."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    CERTIFIED = "certified"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


def generate_model_id() -> str:
    """Generate a stable registry identifier."""
    return f"model_{uuid4().hex}"


class ModelRecord(BaseModel):
    """A single model metadata record stored in SQLite."""

    id: str = Field(default_factory=generate_model_id)
    repo: str = Field(min_length=1)
    family: str = Field(min_length=1)
    params_billion: float = Field(gt=0)
    active_params_billion: float | None = Field(default=None, gt=0)
    is_moe: bool = False
    quant: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    context_len: int = Field(gt=0)
    path: str = Field(min_length=1)
    pool_role: ModelRole | None = None
    status: ModelLifecycleState = ModelLifecycleState.REGISTERED
    tok_per_sec: float | None = Field(default=None, gt=0)
    checksum_sha256: str | None = None
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime | None = None
    lab_cert: LabCertificationStatus | None = None
    notes: str | None = None

    @property
    def size_gb(self) -> float:
        """Return decimal gigabytes for simple profile fit checks."""
        return self.size_bytes / 1_000_000_000
