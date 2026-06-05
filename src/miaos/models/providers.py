"""Model provider interfaces and lightweight implementations."""

import os
from collections.abc import Callable
from importlib import import_module
from importlib.util import find_spec
from typing import Protocol, cast, runtime_checkable

from pydantic import BaseModel, Field

type JsonScalar = bool | int | float | str | None
MLX_LOAD_RETURN_SIZE = 2


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
    """Optional MLX provider backed by `mlx_lm` when installed."""

    def __init__(self, *, default_model_id: str | None = None) -> None:
        """Create an MLX provider with an optional default model id."""
        self.default_model_id = default_model_id or os.getenv("MIAOS_MLX_MODEL")
        self._model_cache: dict[str, tuple[object, object]] = {}

    @property
    def name(self) -> str:
        """Return the stable provider name."""
        return "mlx"

    def is_available(self) -> bool:
        """Return whether MLX inference dependencies are importable."""
        return find_spec("mlx_lm") is not None

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate text through `mlx_lm` without changing the provider protocol."""
        if not self.is_available():
            msg = "MLX provider is unavailable: install mlx-lm to enable local inference"
            raise RuntimeError(msg)

        model_id = request.model_id or self.default_model_id
        if not model_id:
            msg = (
                "MLX provider is available, but no model_id was provided; "
                "set request.model_id or MIAOS_MLX_MODEL"
            )
            raise RuntimeError(msg)

        model, tokenizer = self._load_model(model_id)
        prompt = self._prompt_from_request(request)
        text = self._mlx_generate(
            model=model,
            tokenizer=tokenizer,
            prompt=prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return InferenceResponse(
            text=text,
            provider_name=self.name,
            model_id=model_id,
            trace_id=request.trace_id,
            metadata={
                "mlx_lm": True,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
        )

    def _load_model(self, model_id: str) -> tuple[object, object]:
        """Load and cache an MLX model/tokenizer pair."""
        cached = self._model_cache.get(model_id)
        if cached is not None:
            return cached

        mlx_lm = import_module("mlx_lm")
        load_fn = self._attribute_as_callable(mlx_lm, "load")
        loaded = load_fn(model_id)
        if not isinstance(loaded, tuple) or len(loaded) != MLX_LOAD_RETURN_SIZE:
            msg = "mlx_lm.load must return a (model, tokenizer) tuple"
            raise TypeError(msg)
        model, tokenizer = loaded
        bundle = (model, tokenizer)
        self._model_cache[model_id] = bundle
        return bundle

    @staticmethod
    def _mlx_generate(
        *,
        model: object,
        tokenizer: object,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call `mlx_lm.generate` using the common keyword-compatible API."""
        mlx_lm = import_module("mlx_lm")
        generate_fn = MLXModelProvider._attribute_as_callable(mlx_lm, "generate")
        raw_text = generate_fn(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
            verbose=False,
        )
        if not isinstance(raw_text, str):
            msg = "mlx_lm.generate must return text"
            raise TypeError(msg)
        return raw_text

    @staticmethod
    def _prompt_from_request(request: InferenceRequest) -> str:
        """Build the provider prompt while preserving optional system context."""
        if request.system_prompt:
            return f"{request.system_prompt}\n\n{request.prompt}"
        return request.prompt

    @staticmethod
    def _attribute_as_callable(module: object, name: str) -> Callable[..., object]:
        """Return a callable attribute from a dynamically imported module."""
        attribute = getattr(module, name, None)
        if not callable(attribute):
            msg = f"mlx_lm.{name} is not callable"
            raise TypeError(msg)
        return cast("Callable[..., object]", attribute)


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
