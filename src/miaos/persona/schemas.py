"""Schemas for minimal Persona and `.mia` packages."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def generate_persona_id() -> str:
    """Generate a stable persona identifier."""
    return f"mia_{uuid4().hex}"


class PersonaIdentity(BaseModel):
    """Core identity stored in a `.mia` package."""

    id: str = Field(default_factory=generate_persona_id)
    name: str = Field(min_length=1)
    role: str = Field(default="Virtual personality", min_length=1)
    default_locale: str = Field(default="ru-RU", min_length=2)
    biography_seed: str | None = None


class PersonaCard(BaseModel):
    """Human-editable minimal persona card."""

    identity: PersonaIdentity
    values: list[str] = Field(default_factory=lambda: ["honesty", "care"])

    @field_validator("values")
    @classmethod
    def values_must_not_be_empty(cls, values: list[str]) -> list[str]:
        """Require at least one value anchor."""
        if not values:
            msg = "persona values must not be empty"
            raise ValueError(msg)
        return values


class ModelBinding(BaseModel):
    """Model binding metadata; weights are never stored in `.mia`."""

    provider: str = Field(default="mock", min_length=1)
    model_id: str = Field(default="mock-mia", min_length=1)
    runtime_profile: str | None = None
    role_pool: dict[str, str] = Field(default_factory=dict)


class AutonomyContractRef(BaseModel):
    """Reference to the autonomy contract used by the persona."""

    contract_id: str = Field(default="supervised-default", min_length=1)
    path: str = Field(default="autonomy/contract_ref.json", min_length=1)
    autonomy_ceiling: str = Field(default="L3", pattern=r"^L[0-4]$")


class PersonaManifest(BaseModel):
    """Manifest for a minimal `.mia` directory package."""

    mia_format_version: str = "1.0.0"
    persona_id: str
    name: str
    version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    identity_path: str = "personality/identity.json"
    values_path: str = "personality/values.json"
    model_binding_path: str = "model_binding.json"
    autonomy_contract_ref_path: str = "autonomy/contract_ref.json"
