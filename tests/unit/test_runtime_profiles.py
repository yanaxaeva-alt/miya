"""Tests for runtime profile loading and validation."""

import pytest
from pydantic import ValidationError

from miaos.runtime import RuntimeProfile, list_runtime_profiles, load_runtime_profile

AIR_MEMORY_GB = 32
AIR_CONTEXT_TOKENS = 32768
PRO_MEMORY_GB = 48
PRO_CONTEXT_TOKENS = 65536


def test_lists_runtime_profiles() -> None:
    """Bundled runtime profiles are discoverable."""
    profiles = list_runtime_profiles()

    assert "macbook_air_m4_32gb" in profiles
    assert "macbook_pro_m4pro_48gb" in profiles


def test_loads_air_runtime_profile() -> None:
    """The Air profile encodes conservative development defaults."""
    profile = load_runtime_profile("macbook_air_m4_32gb")

    assert profile.hardware.unified_memory_gb == AIR_MEMORY_GB
    assert profile.always_busy is False
    assert profile.max_context_tokens_default == AIR_CONTEXT_TOKENS
    assert profile.recommended_pool["worker"].candidates


def test_loads_pro_runtime_profile() -> None:
    """The Pro profile allows guarded larger-model integration work."""
    profile = load_runtime_profile("macbook_pro_m4pro_48gb")

    assert profile.hardware.unified_memory_gb == PRO_MEMORY_GB
    assert profile.always_busy == "guarded"
    assert profile.max_context_tokens_default == PRO_CONTEXT_TOKENS
    assert profile.recommended_pool["moe_expert"].candidates


def test_air_profile_rejects_unsafe_large_defaults() -> None:
    """A 32 GB profile cannot silently enable an unsafe large-model default."""
    unsafe_profile = {
        "name": "unsafe_air",
        "role": "dev_and_light_runtime",
        "hardware": {
            "name": "MacBook Air M4",
            "unified_memory_gb": AIR_MEMORY_GB,
            "apple_silicon_generation": "M4",
        },
        "primary_model_tier": "qwen_27b",
        "large_model_mode": "enabled",
        "max_context_tokens_default": PRO_CONTEXT_TOKENS,
        "max_context_tokens_experimental": 131072,
        "background_cycles": "balanced",
        "always_busy": "guarded",
        "thermal_policy": "quiet",
        "vector_db": "sqlite_or_lancedb_light",
        "observability": "decisions_jsonl_only",
        "recommended_pool": {
            "router": {"role": "router", "candidates": [], "max_memory_gb": 0},
            "worker": {"role": "worker", "candidates": [], "max_memory_gb": 0},
            "moe_expert": {"role": "moe_expert", "candidates": [], "max_memory_gb": 0},
            "deep": {"role": "deep", "candidates": [], "max_memory_gb": 0},
        },
        "safety_defaults": {
            "autonomy_ceiling": "L3",
            "require_approval": ["publish"],
            "denied_always": ["financial_transaction"],
        },
    }

    with pytest.raises(ValidationError, match="32 GB profiles cannot enable"):
        RuntimeProfile.model_validate(unsafe_profile)
