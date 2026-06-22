"""Tests for model provider interfaces."""

from typing import Any

import pytest

from miaos.models import InferenceRequest, MLXModelProvider, MockModelProvider, provider_infos
from miaos.models.providers import DEFAULT_MLX_MODEL, MLX_MODEL_ALIASES


def test_mock_provider_generates_deterministic_response() -> None:
    """Mock provider echoes enough request data to prove invocation."""
    provider = MockModelProvider()
    request = InferenceRequest(prompt="hello", model_id="mock-small", trace_id="trace-1")

    response = provider.generate(request)

    assert response.provider_name == "mock"
    assert response.model_id == "mock-small"
    assert response.trace_id == "trace-1"
    assert response.text == "[mock-small] hello"
    assert response.metadata["deterministic"] is True


def test_provider_infos_include_mock_and_mlx() -> None:
    """Provider status includes the always-available mock provider and MLX wrapper."""
    infos = {provider.name: provider for provider in provider_infos()}

    assert infos["mock"].available is True
    assert "mlx" in infos


def test_mlx_provider_fails_explicitly_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MLX wrapper never silently falls back to another provider."""
    provider = MLXModelProvider()
    monkeypatch.setattr(provider, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="MLX provider is unavailable"):
        provider.generate(InferenceRequest(prompt="hello"))


def test_mlx_resolve_model_path_aliases() -> None:
    """Editor model ids map to mlx-community repos."""
    assert MLXModelProvider.resolve_model_path("qwen3.5-8b") == MLX_MODEL_ALIASES["qwen3.5-8b"]
    assert MLXModelProvider.resolve_model_path(None) == DEFAULT_MLX_MODEL
    assert (
        MLXModelProvider.resolve_model_path("mlx-community/Qwen2.5-7B-Instruct-4bit")
        == "mlx-community/Qwen2.5-7B-Instruct-4bit"
    )


def test_mlx_provider_generates_with_mocked_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLX provider delegates to mlx-lm load/generate when dependencies exist."""
    provider = MLXModelProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)

    loaded_paths: list[str] = []

    def fake_load(model_path: str) -> tuple[str, str]:
        loaded_paths.append(model_path)
        return "model", "tokenizer"

    def fake_generate(
        _model: Any,
        _tokenizer: Any,
        prompt: str,
        *,
        max_tokens: int,
        temp: float,
    ) -> str:
        assert max_tokens == 128
        assert temp == 0.2
        return f"mlx-answer:{prompt[:12]}"

    monkeypatch.setattr(provider, "_load_model", fake_load)
    monkeypatch.setattr(provider, "_generate_text", fake_generate)

    response = provider.generate(
        InferenceRequest(
            prompt="Plan a short reply",
            model_id="qwen3.5-8b",
            max_tokens=128,
            temperature=0.2,
            trace_id="trace-mlx",
        )
    )

    assert loaded_paths == [MLX_MODEL_ALIASES["qwen3.5-8b"]]
    assert response.provider_name == "mlx"
    assert response.model_id == MLX_MODEL_ALIASES["qwen3.5-8b"]
    assert response.trace_id == "trace-mlx"
    assert response.text.startswith("mlx-answer:")
    assert response.metadata["mlx_model_path"] == MLX_MODEL_ALIASES["qwen3.5-8b"]
