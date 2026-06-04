"""Core runtime profile models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class ConfigurationError(ValueError):
    """Raised when a runtime profile configuration is invalid."""


@dataclass(frozen=True, slots=True)
class LaunchConfig:
    """Provider-specific launch metadata."""

    model_ref: str
    command: tuple[str, ...]
    host: str = "127.0.0.1"
    port: int = 0
    env: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "model_ref": self.model_ref,
            "command": list(self.command),
            "host": self.host,
            "port": self.port,
            "env": dict(self.env),
        }


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Normalized hardware profile used by the runtime layer."""

    name: str
    machine_family: str
    chip: str
    unified_memory_gb: int
    runtime_memory_budget_gb: int
    profile_tier: str
    intended_uses: tuple[str, ...]
    supports_mlx: bool
    max_parallel_models: int
    notes: tuple[str, ...] = ()

    def can_host(self, model_profile: ModelProfile) -> bool:
        return self.runtime_memory_budget_gb >= model_profile.min_memory_gb

    def matches(self, *, machine_family: str, chip: str, unified_memory_gb: int) -> bool:
        return (
            self.machine_family == machine_family
            and self.chip == chip
            and self.unified_memory_gb <= unified_memory_gb
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "machine_family": self.machine_family,
            "chip": self.chip,
            "unified_memory_gb": self.unified_memory_gb,
            "runtime_memory_budget_gb": self.runtime_memory_budget_gb,
            "profile_tier": self.profile_tier,
            "intended_uses": list(self.intended_uses),
            "supports_mlx": self.supports_mlx,
            "max_parallel_models": self.max_parallel_models,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Configured model option for a runtime profile."""

    id: str
    provider: str
    family: str
    variant: str
    quantization: str
    roles: tuple[str, ...]
    min_memory_gb: int
    recommended_memory_gb: int
    context_window: int
    fallback_ids: tuple[str, ...]
    enabled: bool = True
    launch: LaunchConfig | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def supports_hardware(self, hardware: HardwareProfile) -> bool:
        return self.enabled and hardware.can_host(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "provider": self.provider,
            "family": self.family,
            "variant": self.variant,
            "quantization": self.quantization,
            "roles": list(self.roles),
            "min_memory_gb": self.min_memory_gb,
            "recommended_memory_gb": self.recommended_memory_gb,
            "context_window": self.context_window,
            "fallback_ids": list(self.fallback_ids),
            "enabled": self.enabled,
            "launch": None if self.launch is None else self.launch.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """Complete runtime profile loaded from YAML configuration."""

    name: str
    description: str
    hardware: HardwareProfile
    default_provider: str
    default_model_id: str
    models: tuple[ModelProfile, ...]

    def model_by_id(self, model_id: str) -> ModelProfile:
        for model in self.models:
            if model.id == model_id:
                return model
        raise ConfigurationError(f"Unknown model_id '{model_id}' in profile '{self.name}'.")

    def models_for_provider(self, provider_name: str) -> tuple[ModelProfile, ...]:
        return tuple(model for model in self.models if model.provider == provider_name)

    def default_model(self) -> ModelProfile:
        return self.model_by_id(self.default_model_id)

    def validate(self) -> None:
        if not self.models:
            raise ConfigurationError(
                f"Runtime profile '{self.name}' must declare at least one model."
            )

        known_model_ids = {model.id for model in self.models}
        if self.default_model_id not in known_model_ids:
            raise ConfigurationError(
                f"Runtime profile '{self.name}' references unknown default_model_id "
                f"'{self.default_model_id}'."
            )

        for model in self.models:
            for fallback_id in model.fallback_ids:
                if fallback_id not in known_model_ids:
                    raise ConfigurationError(
                        f"Model '{model.id}' in profile '{self.name}' references unknown "
                        f"fallback '{fallback_id}'."
                    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "default_provider": self.default_provider,
            "default_model_id": self.default_model_id,
            "hardware": self.hardware.to_dict(),
            "models": [model.to_dict() for model in self.models],
        }
