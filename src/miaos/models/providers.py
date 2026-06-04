"""Model provider interfaces and lightweight implementations."""

from importlib.util import find_spec
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

type JsonScalar = bool | int | float | str | None


class InferenceRequest(BaseModel):
    """Provider-neutral inference request."""

    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    model_id: str | None = None
    trace_id: str | None = None
    max_tokens: int = Field(default=256, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class InferenceResponse(BaseModel):
    """Provider-neutral inference response."""

    text: str
    provider_name: str
    model_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    """Runtime-visible model provider status."""

    name: str
    available: bool
    description: str


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol implemented by model providers."""

    @property
    def name(self) -> str:
        """Return the stable provider name."""

    def is_available(self) -> bool:
        """Return whether this provider can execute in the current environment."""

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate an inference response."""


class MockModelProvider:
    """Deterministic provider for tests and development."""

    @property
    def name(self) -> str:
        """Return the stable provider name."""
        return "mock"

    def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Return a deterministic response that proves the provider was invoked."""
        prefix = f"[{request.model_id}]" if request.model_id else "[mock-model]"
        return InferenceResponse(
            text=f"{prefix} {request.prompt}",
            provider_name=self.name,
            model_id=request.model_id,
            trace_id=request.trace_id,
            metadata={"deterministic": True},
        )


class MLXModelProvider:
    """MLX provider interface wrapper.

    This class deliberately does not download or start models. It only reports
    whether the optional MLX dependency is importable and provides a clear error
    if generation is attempted before the real provider implementation is added.
    """

    @property
    def name(self) -> str:
        """Return the stable provider name."""
        return "mlx"

    def is_available(self) -> bool:
        """Return whether MLX inference dependencies are importable."""
        return find_spec("mlx_lm") is not None

    def generate(self, _request: InferenceRequest) -> InferenceResponse:
        """Fail explicitly until real MLX inference is implemented."""
        if not self.is_available():
            msg = "MLX provider is unavailable: install mlx-lm to enable local inference"
            raise RuntimeError(msg)
        msg = "MLX provider wrapper is available, but real generation is not implemented yet"
        raise NotImplementedError(msg)


def available_providers() -> list[ModelProvider]:
    """Return model providers known to the runtime."""
    return [MockModelProvider(), MLXModelProvider()]


def provider_infos() -> list[ProviderInfo]:
    """Return provider status objects suitable for CLI/API display."""
    descriptions = {
        "mock": "Deterministic development and test provider.",
        "mlx": "Optional Apple Silicon MLX provider wrapper.",
    }
    return [
        ProviderInfo(
            name=provider.name,
            available=provider.is_available(),
            description=descriptions[provider.name],
        )
        for provider in available_providers()
    ]
