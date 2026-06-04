"""Action request schemas and autonomy levels."""

from enum import StrEnum

from pydantic import BaseModel, Field


class AutonomyLevel(StrEnum):
    """Implemented autonomy levels. L5 is intentionally absent."""

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class ActionClass(StrEnum):
    """Action classes understood by the MVP Policy Gate."""

    READ = "read"
    ANALYZE = "analyze"
    DRAFT = "draft"
    SANDBOX_WRITE = "sandbox_write"
    PUBLISH = "publish"
    SEND_MESSAGE = "send_message"
    DELETE = "delete"
    WRITE_OUTSIDE_SANDBOX = "write_outside_sandbox"
    FINANCIAL_TRANSACTION = "financial_transaction"
    SELF_MODIFICATION = "self_modification"
    CONTRACT_BYPASS = "contract_bypass"
    DISABLE_GUARDRAILS = "disable_guardrails"
    BYPASS_KILL_SWITCH = "bypass_kill_switch"


class ActionRequest(BaseModel):
    """Request to perform or authorize an action."""

    action_class: ActionClass
    actor: str = Field(default="mia", min_length=1)
    resource: str | None = None
    domain: str | None = None
    description: str | None = None
    trace_id: str | None = None
