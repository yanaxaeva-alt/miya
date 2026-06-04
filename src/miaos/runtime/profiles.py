"""Hardware-aware runtime profile loading and validation."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, Field, PositiveInt, model_validator

AutonomyCeiling = Literal["L0", "L1", "L2", "L3", "L4"]
BackgroundCycles = Literal["conservative", "balanced", "aggressive"]
LargeModelMode = Literal["disabled", "optional_limited", "enabled"]
ModelPoolRole = Literal["router", "worker", "moe_expert", "deep"]
AlwaysBusyMode = bool | Literal["guarded"]
LIGHT_RUNTIME_MEMORY_GB = 32
LIGHT_RUNTIME_MAX_CONTEXT_TOKENS = 32768


class RuntimeProfileError(ValueError):
    """Raised when a runtime profile cannot be loaded or validated."""


class HardwareProfile(BaseModel):
    """Physical hardware characteristics relevant to local inference."""

    name: str = Field(min_length=1)
    unified_memory_gb: PositiveInt
    apple_silicon_generation: str = Field(min_length=1)


class ModelProfile(BaseModel):
    """Model candidates for a single pool role."""

    role: ModelPoolRole
    candidates: list[str] = Field(default_factory=list)
    max_memory_gb: float = Field(ge=0)

    @model_validator(mode="after")
    def candidates_require_memory_budget(self) -> Self:
        """Reject candidates that have no memory budget assigned."""
        if self.candidates and self.max_memory_gb <= 0:
            msg = f"model role {self.role!r} has candidates but no memory budget"
            raise ValueError(msg)
        return self


class SafetyDefaults(BaseModel):
    """Runtime safety defaults derived from the autonomy contract."""

    autonomy_ceiling: AutonomyCeiling
    require_approval: list[str] = Field(default_factory=list)
    denied_always: list[str] = Field(default_factory=list)


class RuntimeProfile(BaseModel):
    """A hardware-aware runtime profile used by model providers and executors."""

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    hardware: HardwareProfile
    primary_model_tier: str = Field(min_length=1)
    large_model_mode: LargeModelMode
    max_context_tokens_default: PositiveInt
    max_context_tokens_experimental: PositiveInt
    background_cycles: BackgroundCycles
    always_busy: AlwaysBusyMode
    thermal_policy: str = Field(min_length=1)
    vector_db: str = Field(min_length=1)
    observability: str = Field(min_length=1)
    recommended_pool: dict[ModelPoolRole, ModelProfile]
    safety_defaults: SafetyDefaults

    @model_validator(mode="after")
    def validate_runtime_constraints(self) -> Self:
        """Validate profile-level safety and hardware constraints."""
        if self.max_context_tokens_experimental < self.max_context_tokens_default:
            msg = "experimental context must be greater than or equal to default context"
            raise ValueError(msg)

        if self.hardware.unified_memory_gb <= LIGHT_RUNTIME_MEMORY_GB:
            self._validate_light_runtime_constraints()

        if not self.safety_defaults.denied_always:
            msg = "runtime profile must define denied_always safety defaults"
            raise ValueError(msg)

        expected_roles: set[ModelPoolRole] = {"router", "worker", "moe_expert", "deep"}
        missing_roles = expected_roles.difference(self.recommended_pool)
        if missing_roles:
            missing = ", ".join(sorted(missing_roles))
            msg = f"runtime profile is missing model pool roles: {missing}"
            raise ValueError(msg)

        for role, model_profile in self.recommended_pool.items():
            if role != model_profile.role:
                msg = f"recommended_pool key {role!r} does not match role {model_profile.role!r}"
                raise ValueError(msg)

        return self

    def _validate_light_runtime_constraints(self) -> None:
        """Validate constraints for <=32 GB development/light runtime profiles."""
        if self.large_model_mode == "enabled":
            msg = "32 GB profiles cannot enable large_model_mode by default"
            raise ValueError(msg)

        if self.max_context_tokens_default > LIGHT_RUNTIME_MAX_CONTEXT_TOKENS:
            msg = "32 GB profiles must default to <=32768 context tokens"
            raise ValueError(msg)

        if self.always_busy is not False:
            msg = "32 GB profiles must disable always_busy by default"
            raise ValueError(msg)

        if self.background_cycles != "conservative":
            msg = "32 GB profiles must use conservative background cycles"
            raise ValueError(msg)


def default_runtime_config_dir() -> Path:
    """Return the default runtime configuration directory for local development."""
    return Path.cwd() / "configs" / "runtime"


def list_runtime_profiles(config_dir: Path | None = None) -> list[str]:
    """List available runtime profile names."""
    directory = config_dir or default_runtime_config_dir()
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.yaml"))


def load_runtime_profile(name: str, config_dir: Path | None = None) -> RuntimeProfile:
    """Load and validate a runtime profile by name."""
    directory = config_dir or default_runtime_config_dir()
    path = directory / f"{name}.yaml"
    if not path.exists():
        msg = f"runtime profile {name!r} not found in {directory}"
        raise RuntimeProfileError(msg)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"runtime profile {name!r} must be a YAML mapping"
        raise RuntimeProfileError(msg)

    try:
        return RuntimeProfile.model_validate(raw)
    except ValueError as exc:
        msg = f"runtime profile {name!r} is invalid: {exc}"
        raise RuntimeProfileError(msg) from exc


def load_all_runtime_profiles(config_dir: Path | None = None) -> list[RuntimeProfile]:
    """Load all available runtime profiles."""
    return [
        load_runtime_profile(name, config_dir=config_dir)
        for name in list_runtime_profiles(config_dir)
    ]
