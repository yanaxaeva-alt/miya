"""Model provider interfaces and lightweight implementations."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from importlib.util import find_spec
from typing import Any, ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, Field

type JsonScalar = bool | int | float | str | None

DEFAULT_MLX_MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
MIYA_MLX_MODEL_ENV = "MIYA_MLX_MODEL"
MIYA_PROVIDER_ENV = "MIYA_PROVIDER"
MIYA_OMLX_BASE_URL_ENV = "MIYA_OMLX_BASE_URL"
MIYA_OMLX_MODEL_ENV = "MIYA_OMLX_MODEL"
MIYA_OMLX_API_KEY_ENV = "MIYA_OMLX_API_KEY"
DEFAULT_OMLX_BASE_URL = "http://127.0.0.1:8010"

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
    default: bool = False
    default_model: str | None = None
    model_ids: list[str] = Field(default_factory=list)


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


class OMLXModelProvider:
    """OpenAI-compatible provider for a local oMLX server."""

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None) -> None:
        """Create an oMLX provider using env defaults when values are omitted."""
        configured_url = base_url or os.environ.get(MIYA_OMLX_BASE_URL_ENV) or DEFAULT_OMLX_BASE_URL
        self.base_url = configured_url.rstrip("/")
        self.api_key = api_key or os.environ.get(MIYA_OMLX_API_KEY_ENV)

    @property
    def name(self) -> str:
        """Return the stable provider name."""
        return "omlx"

    def is_available(self) -> bool:
        """Return whether the local oMLX OpenAI-compatible server responds."""
        try:
            self.list_model_ids(timeout=0.5)
        except (OSError, TimeoutError, ValueError, urllib.error.URLError):
            return False
        return True

    def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate text through oMLX's OpenAI-compatible chat endpoint."""
        model_id = os.environ.get(MIYA_OMLX_MODEL_ENV) or request.model_id or self._first_model_id()
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }
        body = self._request_json("POST", "/v1/chat/completions", payload=payload, timeout=120)
        text = self._extract_text(body)
        return InferenceResponse(
            text=text,
            provider_name=self.name,
            model_id=model_id,
            trace_id=request.trace_id,
            metadata={"omlx_base_url": self.base_url},
        )

    def _first_model_id(self) -> str:
        model_ids = self.list_model_ids(timeout=5)
        if model_ids:
            return model_ids[0]
        msg = "oMLX did not return any model ids from /v1/models"
        raise RuntimeError(msg)

    def list_model_ids(self, *, timeout: float = 5) -> list[str]:
        """Return model ids exposed by the oMLX server."""
        body = self._request_json("GET", "/v1/models", timeout=timeout)
        data = body.get("data")
        model_ids: list[str] = []
        if isinstance(data, list):
            model_ids.extend(
                item["id"]
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            )
        return model_ids

    def selected_model_id(self, *, model_ids: list[str] | None = None) -> str | None:
        """Return the configured oMLX model or first discovered model."""
        configured = os.environ.get(MIYA_OMLX_MODEL_ENV)
        if configured:
            return configured
        ids = model_ids if model_ids is not None else self.list_model_ids(timeout=5)
        return ids[0] if ids else None

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        self._validate_base_url()
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(  # noqa: S310
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if self.api_key:
            request.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
        body = json.loads(raw)
        if not isinstance(body, dict):
            msg = "oMLX returned a non-object JSON response"
            raise TypeError(msg)
        return body

    def _validate_base_url(self) -> None:
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            msg = "oMLX base URL must use http or https"
            raise ValueError(msg)

    @staticmethod
    def _extract_text(body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
        msg = "oMLX response did not contain generated text"
        raise RuntimeError(msg)


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
            return os.environ.get(MIYA_MLX_MODEL_ENV, DEFAULT_MLX_MODEL)
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
    """Return the preferred available provider."""
    env_provider = os.environ.get(MIYA_PROVIDER_ENV)
    if env_provider in {"mock", "omlx", "mlx"}:
        return env_provider
    if OMLXModelProvider().is_available():
        return "omlx"
    if MLXModelProvider().is_available():
        return "mlx"
    return "mock"


def available_providers() -> list[ModelProvider]:
    """Return model providers known to the runtime."""
    return [MockModelProvider(), OMLXModelProvider(), MLXModelProvider()]


def provider_infos() -> list[ProviderInfo]:
    """Return provider status objects suitable for CLI/API display."""
    default_name = default_provider_name()
    mlx = MLXModelProvider()
    omlx = OMLXModelProvider()
    mlx_default = MLXModelProvider.resolve_model_path(None)
    omlx_model_ids: list[str] = []
    if omlx.is_available():
        omlx_model_ids = omlx.list_model_ids(timeout=2)
    omlx_model = omlx.selected_model_id(model_ids=omlx_model_ids)
    mlx_description = (
        f"Local Apple Silicon inference via mlx-lm. Default model: {mlx_default}"
        if mlx.is_available()
        else "Install mlx-lm: cd ~/Documents/miya && uv sync --group mlx"
    )
    omlx_description = (
        f"Local oMLX OpenAI-compatible server at {omlx.base_url}. Default model: {omlx_model}"
        if omlx.is_available()
        else f"Start oMLX on {DEFAULT_OMLX_BASE_URL} or set {MIYA_OMLX_BASE_URL_ENV}"
    )
    descriptions = {
        "mock": "Deterministic development and test provider.",
        "omlx": omlx_description,
        "mlx": mlx_description,
    }
    return [
        ProviderInfo(
            name=provider.name,
            available=provider.is_available(),
            description=descriptions[provider.name],
            default=provider.name == default_name,
            default_model=(
                omlx_model
                if provider.name == "omlx"
                else mlx_default
                if provider.name == "mlx"
                else None
            ),
            model_ids=omlx_model_ids if provider.name == "omlx" else [],
        )
        for provider in available_providers()
    ]


def resolve_provider(provider_name: str) -> ModelProvider:
    """Resolve a provider name to a provider instance."""
    if provider_name == "mock":
        return MockModelProvider()
    if provider_name == "omlx":
        provider = OMLXModelProvider()
        if not provider.is_available():
            msg = "oMLX provider is unavailable: start oMLX or use provider mock/mlx"
            raise ValueError(msg)
        return provider
    if provider_name == "mlx":
        provider = MLXModelProvider()
        if not provider.is_available():
            msg = "MLX provider is unavailable: install mlx-lm or use provider mock"
            raise ValueError(msg)
        return provider
    msg = f"unknown provider: {provider_name}"
    raise ValueError(msg)
