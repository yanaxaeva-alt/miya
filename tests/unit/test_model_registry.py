"""Tests for SQLite model registry and manager selection."""

from pathlib import Path

from miaos.models import (
    LabCertificationStatus,
    ModelLifecycleState,
    ModelManager,
    ModelRegistry,
    ModelRole,
)
from miaos.runtime import load_runtime_profile

SMALL_MODEL_SIZE_BYTES = 8_300_000_000
LARGE_MODEL_SIZE_BYTES = 28_000_000_000
AIR_CONTEXT_TOKENS = 32768
PRO_CONTEXT_TOKENS = 65536


def test_register_list_and_inspect_model(tmp_path: Path) -> None:
    """Model metadata can be registered, listed, and inspected."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")

    record = manager.register_model(
        repo="mlx-community/Qwen3-14B-4bit",
        family="qwen",
        params_billion=14,
        quant="4bit",
        size_bytes=SMALL_MODEL_SIZE_BYTES,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/qwen3-14b-4bit",
        pool_role=ModelRole.WORKER,
        checksum_sha256="abc123",
    )

    assert manager.list_models() == [record]
    inspected = manager.inspect_model(record.id)
    assert inspected.repo == record.repo
    assert inspected.checksum_sha256 == "abc123"


def test_state_transitions_and_lab_cert(tmp_path: Path) -> None:
    """Lifecycle state and lab certification transitions are persisted."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")
    record = manager.register_model(
        repo="local:test",
        family="qwen",
        params_billion=7,
        quant="4bit",
        size_bytes=1,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/test",
    )

    downloaded = manager.mark_downloaded(record.id)
    certified = manager.set_lab_cert(record.id, LabCertificationStatus.PASSED)

    assert downloaded.status == ModelLifecycleState.DOWNLOADED
    assert certified.lab_cert == LabCertificationStatus.PASSED
    assert manager.inspect_model(record.id).lab_cert == LabCertificationStatus.PASSED


def test_select_model_for_air_profile_prefers_safe_fitting_worker(tmp_path: Path) -> None:
    """Air profile selection rejects oversized workers and chooses a fitting model."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")
    fitting = manager.register_model(
        repo="mlx-community/Qwen3-14B-4bit",
        family="qwen",
        params_billion=14,
        quant="4bit",
        size_bytes=SMALL_MODEL_SIZE_BYTES,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/qwen3-14b-4bit",
        pool_role=ModelRole.WORKER,
    )
    oversized = manager.register_model(
        repo="mlx-community/Qwen3-27B-8bit",
        family="qwen",
        params_billion=27,
        quant="8bit",
        size_bytes=LARGE_MODEL_SIZE_BYTES,
        context_len=PRO_CONTEXT_TOKENS,
        path="/models/qwen3-27b-8bit",
        pool_role=ModelRole.WORKER,
    )
    manager.set_lab_cert(fitting.id, LabCertificationStatus.PASSED)
    manager.set_lab_cert(oversized.id, LabCertificationStatus.PASSED)

    selected = manager.select_model_for_profile(load_runtime_profile("macbook_air_m4_32gb"))

    assert selected is not None
    assert selected.id == fitting.id


def test_select_model_for_pro_profile_can_choose_deep_model(tmp_path: Path) -> None:
    """Pro profile selection can choose a large deep-role model that fits its budget."""
    manager = ModelManager(ModelRegistry(tmp_path / "models.sqlite3"))
    deep = manager.register_model(
        repo="mlx-community/Qwen3-27B-8bit",
        family="qwen",
        params_billion=27,
        quant="8bit",
        size_bytes=LARGE_MODEL_SIZE_BYTES,
        context_len=PRO_CONTEXT_TOKENS,
        path="/models/qwen3-27b-8bit",
        pool_role=ModelRole.DEEP,
    )
    manager.set_lab_cert(deep.id, LabCertificationStatus.CERTIFIED)

    selected = manager.select_model_for_profile(
        load_runtime_profile("macbook_pro_m4pro_48gb"),
        role=ModelRole.DEEP,
    )

    assert selected is not None
    assert selected.id == deep.id


def test_failed_lab_cert_is_never_selected(tmp_path: Path) -> None:
    """Failed lab certificates are excluded from model selection."""
    manager = ModelManager.from_path(tmp_path / "models.sqlite3")
    failed = manager.register_model(
        repo="local:failed",
        family="qwen",
        params_billion=7,
        quant="4bit",
        size_bytes=1,
        context_len=AIR_CONTEXT_TOKENS,
        path="/models/failed",
        pool_role=ModelRole.WORKER,
    )
    manager.set_lab_cert(failed.id, LabCertificationStatus.FAILED)

    selected = manager.select_model_for_profile(load_runtime_profile("macbook_air_m4_32gb"))

    assert selected is None
