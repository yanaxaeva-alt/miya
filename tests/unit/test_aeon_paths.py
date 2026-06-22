"""Tests for AEON data directory resolution."""

import os
from pathlib import Path

from aeon.paths import resolve_data_dir


def test_resolve_data_dir_defaults_to_miaos(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MIYA_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_data_dir() == Path(".miaos")


def test_resolve_data_dir_honors_env(monkeypatch) -> None:
    monkeypatch.setenv("MIYA_DATA_DIR", "/tmp/custom-miaos")
    assert resolve_data_dir() == Path("/tmp/custom-miaos")


def test_resolve_data_dir_explicit_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MIYA_DATA_DIR", "/tmp/ignored")
    assert resolve_data_dir(tmp_path) == tmp_path
