"""Tests for AEON data directory resolution."""

from pathlib import Path

import pytest

from aeon.paths import resolve_data_dir


def test_resolve_data_dir_defaults_to_miaos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MIYA_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_data_dir() == Path(".miaos")


def test_resolve_data_dir_honors_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    custom_dir = tmp_path / "custom-miaos"
    monkeypatch.setenv("MIYA_DATA_DIR", str(custom_dir))
    assert resolve_data_dir() == custom_dir


def test_resolve_data_dir_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MIYA_DATA_DIR", str(tmp_path / "ignored"))
    assert resolve_data_dir(tmp_path) == tmp_path
