"""Tests for model provider interfaces."""

from typing import Any

import pytest

from miaos.models import (
    InferenceRequest,
    MLXModelProvider,
    MockModelProvider,
    OMLXModelProvider,
    provider_infos,
)
from miaos.models.providers import (
    DEFAULT_MLX_MODEL,
    MIYA_MLX_MODEL_ENV,
    MIYA_OMLX_MODEL_ENV,
    MIYA_PROVIDER_ENV,
    MLX_MODEL_ALIASES,
    default_provider_name,
)


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
    assert "omlx" in infos
    assert "mlx" in infos


def test_default_provider_can_be_forced_to_omlx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can choose oMLX as the main provider through env."""
    monkeypatch.setenv(MIYA_PROVIDER_ENV, "omlx")

    assert default_provider_name() == "omlx"


def test_provider_infos_mark_default_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider metadata tells the editor which provider is actually selected."""
    monkeypatch.setenv(MIYA_PROVIDER_ENV, "omlx")

    infos = {provider.name: provider for provider in provider_infos()}

    assert infos["omlx"].default is True
    assert infos["mlx"].default is False


def test_omlx_provider_generates_with_openai_compatible_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OMLX provider speaks the OpenAI-compatible chat/completions protocol."""
    provider = OMLXModelProvider(base_url="http://127.0.0.1:8010")
    monkeypatch.delenv(MIYA_OMLX_MODEL_ENV, raising=False)
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request_json(
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        calls.append((method, path, payload))
        assert timeout > 0
        if path == "/v1/models":
            return {"data": [{"id": "qwen-big"}]}
        return {"choices": [{"message": {"content": "local oMLX answer"}}]}

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    response = provider.generate(
        InferenceRequest(prompt="hello", system_prompt="be concise", trace_id="trace-omlx")
    )

    assert response.provider_name == "omlx"
    assert response.model_id == "qwen-big"
    assert response.trace_id == "trace-omlx"
    assert response.text == "local oMLX answer"
    assert calls[-1][0] == "POST"
    assert calls[-1][1] == "/v1/chat/completions"
    assert calls[-1][2]
    assert calls[-1][2]["model"] == "qwen-big"


def test_omlx_provider_uses_env_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The loaded oMLX model overrides persona/request model ids."""
    provider = OMLXModelProvider(base_url="http://127.0.0.1:8010")
    monkeypatch.setenv(MIYA_OMLX_MODEL_ENV, "better-local-model")

    def fake_request_json(
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/v1/chat/completions"
        assert payload
        assert payload["model"] == "better-local-model"
        assert timeout > 0
        return {"choices": [{"message": {"content": "answer"}}]}

    monkeypatch.setattr(provider, "_request_json", fake_request_json)

    response = provider.generate(InferenceRequest(prompt="hello", model_id="mock-aeon"))

    assert response.model_id == "better-local-model"


def test_provider_infos_show_mlx_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider metadata makes the selected MLX default visible to the editor."""
    monkeypatch.setenv(MIYA_MLX_MODEL_ENV, "/Users/yana/.cache/mlx/visible-model")
    monkeypatch.setattr(MLXModelProvider, "is_available", lambda _self: True)

    infos = {provider.name: provider for provider in provider_infos()}

    assert "/Users/yana/.cache/mlx/visible-model" in infos["mlx"].description


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


def test_mlx_resolve_model_path_uses_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local deployments can choose the default MLX model without code changes."""
    monkeypatch.setenv(MIYA_MLX_MODEL_ENV, "/Users/yana/.cache/mlx/my-model")

    assert MLXModelProvider.resolve_model_path(None) == "/Users/yana/.cache/mlx/my-model"


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
