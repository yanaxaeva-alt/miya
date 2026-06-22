"""Tests for runtime-profile model compatibility warnings."""

from pathlib import Path

from miaos.models import (
    LabCertificationStatus,
    ModelManager,
    ModelRole,
    evaluate_models_for_profile,
)
from miaos.runtime import load_runtime_profile

SMALL_MODEL_SIZE_BYTES = 8_300_000_000
LARGE_MODEL_SIZE_BYTES = 28_000_000_000
AIR_CONTEXT_TOKENS = 32768
PRO_CONTEXT_TOKENS = 65536


def test_compatibility_flags_oversized_worker_on_air_profile(tmp_path: Path) -> None:
    """Oversized workers are marked incompatible on the Air profile."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")
    fitting = manager.register_model(
        repo="local:fit",
        family="qwen",
        params_billion=14,
        quant="4bit",
        size_bytes=SMALL_MODEL_SIZE_BYTES,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/fit",
        pool_role=ModelRole.WORKER,
    )
    oversized = manager.register_model(
        repo="local:big",
        family="qwen",
        params_billion=27,
        quant="8bit",
        size_bytes=LARGE_MODEL_SIZE_BYTES,
        context_len=PRO_CONTEXT_TOKENS,
        path="/models/big",
        pool_role=ModelRole.WORKER,
    )
    manager.set_lab_cert(fitting.id, LabCertificationStatus.PASSED)
    manager.set_lab_cert(oversized.id, LabCertificationStatus.PASSED)

    profile = load_runtime_profile("macbook_air_m4_32gb")
    selected = manager.select_model_for_profile(profile)
    reports = evaluate_models_for_profile(
        manager.list_models(),
        profile,
        recommended_model_id=selected.id if selected else None,
    )
    by_id = {report.model_id: report for report in reports}

    assert by_id[fitting.id].selectable is True
    assert by_id[fitting.id].recommended is True
    assert by_id[oversized.id].selectable is False
    assert by_id[oversized.id].compatible is False
    assert any(warning.code == "memory_over_budget" for warning in by_id[oversized.id].warnings)


def test_compatibility_warns_when_lab_cert_missing(tmp_path: Path) -> None:
    """Missing lab certification produces a warning but keeps model selectable if it fits."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")
    record = manager.register_model(
        repo="local:uncertified",
        family="qwen",
        params_billion=7,
        quant="4bit",
        size_bytes=SMALL_MODEL_SIZE_BYTES,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/uncertified",
        pool_role=ModelRole.WORKER,
    )

    profile = load_runtime_profile("macbook_air_m4_32gb")
    report = evaluate_models_for_profile(manager.list_models(), profile)[0]

    assert report.model_id == record.id
    assert report.selectable is True
    assert any(warning.code == "lab_cert_missing" for warning in report.warnings)
