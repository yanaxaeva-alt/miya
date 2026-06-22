"""Model provider interfaces and lightweight implementations."""

from importlib.util import find_spec
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, Field

type JsonScalar = bool | int | float | str | None

DEFAULT_MLX_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

MLX_MODEL_ALIASES: dict[str, str] = {
    "qwen3.5-8b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "qwen3.5-coder-7b": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "qwen3.5-4b": "mlx-community/Qwen2.5-3B-Instruct-4bit",
}


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
    """Apple Silicon MLX provider backed by mlx-lm."""

    _cache: ClassVar[dict[str, tuple[Any, Any]]] = {}

    @property
    def name(self) -> str:
        """Return the stable provider name."""
        return "mlx"

    def is_available(self) -> bool:
        """Return whether MLX inference dependencies are importable."""
        return find_spec("mlx_lm") is not None

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate text with mlx-lm for the resolved model path."""
        if not self.is_available():
            msg = "MLX provider is unavailable: install mlx-lm to enable local inference"
            raise RuntimeError(msg)

        model_path = self.resolve_model_path(request.model_id)
        prompt = self._build_prompt(request)
        model, tokenizer = self._load_model(model_path)
        text = self._generate_text(
            model,
            tokenizer,
            prompt,
            max_tokens=request.max_tokens,
            temp=request.temperature,
        )

        return InferenceResponse(
            text=text,
            provider_name=self.name,
            model_id=model_path,
            trace_id=request.trace_id,
            metadata={"mlx_model_path": model_path},
        )

    @staticmethod
    def resolve_model_path(model_id: str | None) -> str:
        """Map editor/registry ids to an mlx-lm model path or HuggingFace repo."""
        if not model_id:
            return DEFAULT_MLX_MODEL
        if model_id in MLX_MODEL_ALIASES:
            return MLX_MODEL_ALIASES[model_id]
        if model_id.startswith(("mlx-community/", "local:", "/")):
            return model_id
        if "/" in model_id:
            return model_id
        return MLX_MODEL_ALIASES.get(model_id, DEFAULT_MLX_MODEL)

    @staticmethod
    def _build_prompt(request: InferenceRequest) -> str:
        """Combine optional system prompt with the user prompt."""
        if request.system_prompt:
            return f"{request.system_prompt.strip()}\n\n{request.prompt}"
        return request.prompt

    def _load_model(self, model_path: str) -> tuple[Any, Any]:
        """Load and cache a model/tokenizer pair."""
        cached = self._cache.get(model_path)
        if cached is not None:
            return cached

        from mlx_lm import load

        loaded = load(model_path)
        self._cache[model_path] = loaded
        return loaded

    @staticmethod
    def _generate_text(
        model: Any,
        tokenizer: Any,
        prompt: str,
        *,
        max_tokens: int,
        temp: float,
    ) -> str:
        """Run mlx-lm generation for one prompt."""
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        return generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=temp),
            verbose=False,
        )


def default_provider_name() -> str:
    """Return mlx when available, otherwise mock."""
    if MLXModelProvider().is_available():
        return "mlx"
    return "mock"


def available_providers() -> list[ModelProvider]:
    """Return model providers known to the runtime."""
    return [MockModelProvider(), MLXModelProvider()]


def provider_infos() -> list[ProviderInfo]:
    """Return provider status objects suitable for CLI/API display."""
    mlx = MLXModelProvider()
    mlx_description = (
        "Local Apple Silicon inference via mlx-lm (Qwen aliases from Model Studio)."
        if mlx.is_available()
        else "Install mlx-lm: cd ~/Documents/miya && uv sync --group mlx"
    )
    descriptions = {
        "mock": "Deterministic development and test provider.",
        "mlx": mlx_description,
    }
    return [
        ProviderInfo(
            name=provider.name,
            available=provider.is_available(),
            description=descriptions[provider.name],
        )
        for provider in available_providers()
    ]


def resolve_provider(provider_name: str) -> ModelProvider:
    """Resolve a provider name to a provider instance."""
    if provider_name == "mock":
        return MockModelProvider()
    if provider_name == "mlx":
        provider = MLXModelProvider()
        if not provider.is_available():
            msg = "MLX provider is unavailable: install mlx-lm or use provider mock"
            raise ValueError(msg)
        return provider
    msg = f"unknown provider: {provider_name}"
    raise ValueError(msg)
