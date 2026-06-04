import pytest

from miaos.runtime import (
    HardwareProfile,
    MockModelProvider,
    ModelProfile,
    RuntimeCatalog,
    RuntimeProfile,
)
from miaos.runtime.providers import MLXModelProvider, ModelResolutionError


def test_mlx_provider_uses_explicit_fallback_for_air_profile() -> None:
    catalog = RuntimeCatalog.from_directory()
    profile = catalog.get("macbook_air_m4_32gb")
    provider = MLXModelProvider()

    selection = provider.resolve_model(profile, requested_model_id="qwen3.6-27b-8bit")

    assert selection.used_fallback is True
    assert selection.selected_model.id == "qwen3.6-14b-4bit"
    assert selection.resolution_path == ("qwen3.6-27b-8bit", "qwen3.6-14b-4bit")


def test_mlx_provider_keeps_target_model_when_budget_supports_it() -> None:
    catalog = RuntimeCatalog.from_directory()
    profile = catalog.get("macbook_pro_m4pro_48gb")
    provider = MLXModelProvider()

    selection = provider.resolve_model(profile)

    assert selection.used_fallback is False
    assert selection.selected_model.id == "qwen3.6-27b-8bit"


def test_mock_provider_requires_explicit_fallback() -> None:
    profile = RuntimeProfile(
        name="test_mock_profile",
        description="mock profile",
        default_provider="mock",
        default_model_id="mock-large",
        hardware=HardwareProfile(
            name="Mock Hardware",
            machine_family="test_machine",
            chip="test_chip",
            unified_memory_gb=16,
            runtime_memory_budget_gb=16,
            profile_tier="test",
            intended_uses=("tests",),
            supports_mlx=False,
            max_parallel_models=1,
        ),
        models=(
            ModelProfile(
                id="mock-large",
                provider="mock",
                family="mock",
                variant="large",
                quantization="none",
                roles=("target",),
                min_memory_gb=4,
                recommended_memory_gb=4,
                context_window=1024,
                fallback_ids=(),
            ),
        ),
    )
    profile.validate()

    provider = MockModelProvider(unavailable_model_ids={"mock-large"})

    with pytest.raises(ModelResolutionError, match="No explicit fallback configured"):
        provider.resolve_model(profile)
