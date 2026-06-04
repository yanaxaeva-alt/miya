"""Tests for model provider interfaces."""

import pytest

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
        with pytest.raises(NotImplementedError, match="real generation is not implemented"):
            provider.generate(request)
    else:
        with pytest.raises(RuntimeError, match="MLX provider is unavailable"):
            provider.generate(request)
