"""Model provider interfaces and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from shutil import which
from typing import Protocol, runtime_checkable

from miaos.runtime.profiles import HardwareProfile, ModelProfile, RuntimeProfile


class ModelResolutionError(RuntimeError):
    """Raised when a model cannot be resolved using explicit fallback rules."""


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """Inspectable provider metadata."""

    name: str
    description: str
    executable: str | None
    executable_found: bool
    dry_run_only: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "executable": self.executable,
            "executable_found": self.executable_found,
            "dry_run_only": self.dry_run_only,
        }


@dataclass(frozen=True, slots=True)
class ResolvedModelSelection:
    """Result of model selection with explicit fallback trail."""

    requested_model_id: str
    selected_model: ModelProfile
    provider_name: str
    used_fallback: bool
    resolution_path: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_model_id": self.requested_model_id,
            "selected_model": self.selected_model.to_dict(),
            "provider_name": self.provider_name,
            "used_fallback": self.used_fallback,
            "resolution_path": list(self.resolution_path),
            "reason": self.reason,
        }


@runtime_checkable
class ModelProvider(Protocol):
    """Provider interface for model listing and resolution."""

    def provider_name(self) -> str:
        """Return unique provider name."""

    def description(self) -> str:
        """Return provider description."""

    def status(self) -> ProviderStatus:
        """Return provider inspection information."""

    def list_models(self, runtime_profile: RuntimeProfile) -> tuple[ModelProfile, ...]:
        """Return models owned by this provider for a given runtime profile."""

    def resolve_model(
        self, runtime_profile: RuntimeProfile, requested_model_id: str | None = None
    ) -> ResolvedModelSelection:
        """Resolve a model with explicit fallback."""


class BaseModelProvider(ABC):
    """Shared provider behavior."""

    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def _is_model_available(self, model: ModelProfile, hardware: HardwareProfile) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _unavailability_reason(self, model: ModelProfile, hardware: HardwareProfile) -> str:
        raise NotImplementedError

    def list_models(self, runtime_profile: RuntimeProfile) -> tuple[ModelProfile, ...]:
        return runtime_profile.models_for_provider(self.provider_name())

    def resolve_model(
        self, runtime_profile: RuntimeProfile, requested_model_id: str | None = None
    ) -> ResolvedModelSelection:
        request = requested_model_id or runtime_profile.default_model_id
        resolution_path: list[str] = []
        visited: set[str] = set()
        current_model_id = request
        last_reason = ""

        while True:
            if current_model_id in visited:
                chain = " -> ".join(resolution_path + [current_model_id])
                raise ModelResolutionError(f"Fallback cycle detected for '{chain}'.")
            visited.add(current_model_id)
            resolution_path.append(current_model_id)

            current_model = runtime_profile.model_by_id(current_model_id)
            if current_model.provider != self.provider_name():
                last_reason = (
                    f"Model '{current_model.id}' belongs to provider '{current_model.provider}', "
                    f"not '{self.provider_name()}'."
                )
            elif self._is_model_available(current_model, runtime_profile.hardware):
                return ResolvedModelSelection(
                    requested_model_id=request,
                    selected_model=current_model,
                    provider_name=self.provider_name(),
                    used_fallback=current_model.id != request,
                    resolution_path=tuple(resolution_path),
                    reason=(
                        "requested-model"
                        if current_model.id == request
                        else f"explicit-fallback after {last_reason}"
                    ),
                )
            else:
                last_reason = self._unavailability_reason(current_model, runtime_profile.hardware)

            if not current_model.fallback_ids:
                raise ModelResolutionError(
                    f"Unable to resolve '{request}' for provider '{self.provider_name()}': "
                    f"{last_reason}. No explicit fallback configured."
                )

            current_model_id = current_model.fallback_ids[0]


class MockModelProvider(BaseModelProvider):
    """Deterministic provider used for tests and dry-run inspection."""

    def __init__(self, unavailable_model_ids: Collection[str] = ()) -> None:
        self._unavailable_model_ids = frozenset(unavailable_model_ids)

    def provider_name(self) -> str:
        return "mock"

    def description(self) -> str:
        return "In-memory provider for tests and deterministic dry runs."

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.provider_name(),
            description=self.description(),
            executable=None,
            executable_found=True,
            dry_run_only=True,
        )

    def _is_model_available(self, model: ModelProfile, hardware: HardwareProfile) -> bool:
        return model.id not in self._unavailable_model_ids and model.supports_hardware(hardware)

    def _unavailability_reason(self, model: ModelProfile, hardware: HardwareProfile) -> str:
        if model.id in self._unavailable_model_ids:
            return f"mock marked '{model.id}' unavailable"
        return (
            f"runtime memory budget {hardware.runtime_memory_budget_gb}GB is below "
            f"required {model.min_memory_gb}GB"
        )


class MLXModelProvider(BaseModelProvider):
    """MLX provider wrapper without mandatory live model startup."""

    _EXECUTABLE = "mlx_lm.server"

    def provider_name(self) -> str:
        return "mlx"

    def description(self) -> str:
        return "MLX-backed provider wrapper with launch metadata and dry-run inspection."

    def status(self) -> ProviderStatus:
        executable_path = which(self._EXECUTABLE)
        return ProviderStatus(
            name=self.provider_name(),
            description=self.description(),
            executable=executable_path,
            executable_found=executable_path is not None,
            dry_run_only=True,
        )

    def build_launch_command(self, model: ModelProfile) -> tuple[str, ...]:
        if model.launch is None:
            raise ModelResolutionError(
                f"Model '{model.id}' does not define MLX launch metadata."
            )
        return model.launch.command

    def _is_model_available(self, model: ModelProfile, hardware: HardwareProfile) -> bool:
        return hardware.supports_mlx and model.supports_hardware(hardware)

    def _unavailability_reason(self, model: ModelProfile, hardware: HardwareProfile) -> str:
        if not hardware.supports_mlx:
            return f"hardware profile '{hardware.name}' does not support MLX"
        return (
            f"runtime memory budget {hardware.runtime_memory_budget_gb}GB is below "
            f"required {model.min_memory_gb}GB"
        )


def get_model_providers() -> tuple[ModelProvider, ...]:
    """Return the built-in provider registry."""

    return (MockModelProvider(), MLXModelProvider())
