"""Tests for model provider interfaces."""

import sys
from importlib.machinery import ModuleSpec
from types import ModuleType

import pytest

import miaos.models.providers as provider_module
from miaos.models import InferenceRequest, MLXModelProvider, MockModelProvider, provider_infos


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


def test_mlx_provider_fails_explicitly_when_unavailable() -> None:
    """MLX wrapper never silently falls back to another provider."""
    provider = MLXModelProvider()
    request = InferenceRequest(prompt="hello")

    if provider.is_available():
        with pytest.raises(RuntimeError, match="no model_id was provided"):
            provider.generate(request)
    else:
        with pytest.raises(RuntimeError, match="MLX provider is unavailable"):
            provider.generate(request)


def test_mlx_provider_uses_mlx_lm_and_caches_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLX provider calls mlx_lm.load/generate and reuses loaded models."""
    calls: dict[str, list[str]] = {"load": [], "generate_prompts": []}
    module = ModuleType("mlx_lm")

    def fake_load(model_id: str) -> tuple[object, object]:
        calls["load"].append(model_id)
        return object(), object()

    def fake_generate(
        _model: object,
        _tokenizer: object,
        *,
        prompt: str,
        max_tokens: int,
        temp: float,
        verbose: bool,
    ) -> str:
        calls["generate_prompts"].append(prompt)
        return f"generated:{max_tokens}:{temp}:{verbose}:{prompt}"

    module.load = fake_load  # type: ignore[attr-defined]
    module.generate = fake_generate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_lm", module)
    monkeypatch.setattr(
        provider_module,
        "find_spec",
        lambda name: ModuleSpec(name, loader=None) if name == "mlx_lm" else None,
    )
    provider = MLXModelProvider()
    request = InferenceRequest(
        prompt="hello",
        system_prompt="system",
        model_id="local/mlx-test",
        trace_id="trace-mlx",
        max_tokens=7,
        temperature=0.5,
    )

    first = provider.generate(request)
    second = provider.generate(request)

    assert first.provider_name == "mlx"
    assert first.model_id == "local/mlx-test"
    assert first.trace_id == "trace-mlx"
    assert first.text == "generated:7:0.5:False:system\n\nhello"
    assert first.metadata["mlx_lm"] is True
    assert second.text == first.text
    assert calls["load"] == ["local/mlx-test"]
    assert calls["generate_prompts"] == ["system\n\nhello", "system\n\nhello"]
