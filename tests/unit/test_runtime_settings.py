"""Tests for persistent runtime settings."""

import os
from pathlib import Path

import pytest

from miaos.models.providers import MIYA_OMLX_BASE_URL_ENV, MIYA_OMLX_MODEL_ENV, MIYA_PROVIDER_ENV
from miaos.settings import RuntimeSettingsStore, apply_runtime_settings


def test_runtime_settings_persist_and_apply_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selected local model settings survive process restarts."""
    monkeypatch.delenv(MIYA_PROVIDER_ENV, raising=False)
    monkeypatch.delenv(MIYA_OMLX_BASE_URL_ENV, raising=False)
    monkeypatch.delenv(MIYA_OMLX_MODEL_ENV, raising=False)

    store = RuntimeSettingsStore(tmp_path / "settings.json")
    store.select_model(provider="omlx", model_id="Qwen3.5-9B-8bit", base_url="http://127.0.0.1:8010")

    loaded = store.load()
    apply_runtime_settings(loaded)

    assert loaded.provider == "omlx"
    assert loaded.omlx_model == "Qwen3.5-9B-8bit"
    assert os.environ[MIYA_PROVIDER_ENV] == "omlx"
    assert os.environ[MIYA_OMLX_MODEL_ENV] == "Qwen3.5-9B-8bit"
    assert os.environ[MIYA_OMLX_BASE_URL_ENV] == "http://127.0.0.1:8010"

    monkeypatch.delenv(MIYA_PROVIDER_ENV, raising=False)
    monkeypatch.delenv(MIYA_OMLX_MODEL_ENV, raising=False)
    monkeypatch.delenv(MIYA_OMLX_BASE_URL_ENV, raising=False)
