import hashlib
from pathlib import Path

import pytest

from miaos.model_manager import LabCertState, ModelLifecycleState, ModelManager
from miaos.runtime.providers import ModelResolutionError


def _write_model_file(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_register_list_and_inspect(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    model_path = _write_model_file(tmp_path / "model.bin", b"alpha-model")
    manager = ModelManager(db_path=db_path)

    registered = manager.register_model(
        model_id="test-model",
        provider="mlx",
        family="qwen3.6",
        variant="8b",
        quantization="4bit",
        context_len=16384,
        path=model_path,
        pool_role="worker",
        trace_id="trace-register",
    )

    assert registered.status is ModelLifecycleState.REGISTERED
    assert registered.sha256 == _sha256(b"alpha-model")

    listed = manager.list_models()
    assert len(listed) == 1
    assert listed[0].id == "test-model"

    inspected = manager.get_model("test-model")
    assert inspected is not None
    assert inspected.to_dict()["trace_id"] == "trace-register"

    events = manager.list_events("test-model")
    assert len(events) == 1
    assert events[0]["event_type"] == "register_model"


def test_state_transitions_download_then_register_then_lab_cert(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    downloaded_path = _write_model_file(tmp_path / "downloaded.bin", b"beta-model")
    registered_path = _write_model_file(tmp_path / "registered.bin", b"gamma-model")
    manager = ModelManager(db_path=db_path)

    downloaded = manager.mark_downloaded(
        model_id="transition-model",
        provider="mlx",
        family="qwen3.6",
        variant="14b",
        quantization="4bit",
        context_len=32768,
        path=downloaded_path,
        trace_id="trace-download",
    )
    assert downloaded.status is ModelLifecycleState.DOWNLOADED
    assert downloaded.sha256 == _sha256(b"beta-model")

    registered = manager.register_model(
        model_id="transition-model",
        provider="mlx",
        family="qwen3.6",
        variant="14b",
        quantization="4bit",
        context_len=32768,
        path=registered_path,
        trace_id="trace-register",
    )
    assert registered.status is ModelLifecycleState.REGISTERED
    assert registered.sha256 == _sha256(b"gamma-model")

    certified = manager.set_lab_cert(
        "transition-model",
        LabCertState.PASSED,
        trace_id="trace-cert",
    )
    assert certified.lab_cert is LabCertState.PASSED

    events = manager.list_events("transition-model")
    assert [event["event_type"] for event in events] == [
        "mark_downloaded",
        "register_model",
        "set_lab_cert",
    ]


def test_select_model_for_air_32gb_uses_explicit_fallback(tmp_path: Path) -> None:
    manager = ModelManager(db_path=tmp_path / "registry.sqlite3")
    target_path = _write_model_file(tmp_path / "target.bin", b"target")
    fallback_path = _write_model_file(tmp_path / "fallback.bin", b"fallback")

    manager.register_model(
        model_id="qwen3.6-27b-8bit",
        provider="mlx",
        family="qwen3.6",
        variant="27b",
        quantization="8bit",
        context_len=32768,
        path=target_path,
    )
    manager.set_lab_cert("qwen3.6-27b-8bit", LabCertState.PASSED)
    manager.register_model(
        model_id="qwen3.6-14b-4bit",
        provider="mlx",
        family="qwen3.6",
        variant="14b",
        quantization="4bit",
        context_len=32768,
        path=fallback_path,
    )
    manager.set_lab_cert("qwen3.6-14b-4bit", LabCertState.PASSED)

    selection = manager.select_model_for_profile(
        "macbook_air_m4_32gb",
        requested_model_id="qwen3.6-27b-8bit",
        trace_id="trace-air-select",
    )

    assert selection.used_fallback is True
    assert selection.selected_record.id == "qwen3.6-14b-4bit"
    assert selection.resolution_path == ("qwen3.6-27b-8bit", "qwen3.6-14b-4bit")
    assert selection.trace_id == "trace-air-select"


def test_select_model_for_pro_48gb_keeps_primary_model(tmp_path: Path) -> None:
    manager = ModelManager(db_path=tmp_path / "registry.sqlite3")
    target_path = _write_model_file(tmp_path / "target.bin", b"target")
    fallback_path = _write_model_file(tmp_path / "fallback.bin", b"fallback")

    manager.register_model(
        model_id="qwen3.6-27b-8bit",
        provider="mlx",
        family="qwen3.6",
        variant="27b",
        quantization="8bit",
        context_len=32768,
        path=target_path,
    )
    manager.set_lab_cert("qwen3.6-27b-8bit", LabCertState.PASSED)
    manager.register_model(
        model_id="qwen3.6-14b-4bit",
        provider="mlx",
        family="qwen3.6",
        variant="14b",
        quantization="4bit",
        context_len=32768,
        path=fallback_path,
    )
    manager.set_lab_cert("qwen3.6-14b-4bit", LabCertState.PASSED)

    selection = manager.select_model_for_profile("macbook_pro_m4pro_48gb")

    assert selection.used_fallback is False
    assert selection.selected_record.id == "qwen3.6-27b-8bit"


def test_select_model_for_profile_requires_explicit_fallback(tmp_path: Path) -> None:
    manager = ModelManager(db_path=tmp_path / "registry.sqlite3")

    with pytest.raises(ModelResolutionError, match="No explicit fallback configured"):
        manager.select_model_for_profile(
            "macbook_air_m4_32gb",
            requested_model_id="qwen3.6-8b-4bit",
        )
