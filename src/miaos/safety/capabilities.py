"""Scoped capability tokens for allowed actions."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from miaos.safety.actions import ActionClass


def generate_capability_id() -> str:
    """Generate a capability token id."""
    return f"cap_{uuid4().hex}"


class CapabilityToken(BaseModel):
    """Narrow, temporary authorization for one allowed action."""

    token_id: str = Field(default_factory=generate_capability_id)
    issued_to: str
    action_class: ActionClass
    resources: dict[str, str] = Field(default_factory=dict)
    constraints: dict[str, str | int | bool] = Field(default_factory=dict)
    ttl_seconds: int = Field(default=300, gt=0)
    single_use: bool = True
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    audit_ref: str | None = None
