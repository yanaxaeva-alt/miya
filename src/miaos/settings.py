"""Persistent MiaOS runtime settings."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from miaos.models.providers import (
    MIYA_MLX_MODEL_ENV,
    MIYA_OMLX_BASE_URL_ENV,
    MIYA_OMLX_MODEL_ENV,
    MIYA_PROVIDER_ENV,
)


class RuntimeSettings(BaseModel):
    """User-selected runtime settings persisted under the MiaOS data dir."""

    provider: str | None = None
    omlx_base_url: str | None = None
    omlx_model: str | None = None
    mlx_model: str | None = None
    updated_at: str | None = None


class RuntimeSettingsStore:
    """JSON-backed settings store."""

    def __init__(self, path: Path) -> None:
        """Create a store at the given JSON path."""
        self.path = path

    def load(self) -> RuntimeSettings:
        """Load settings, returning defaults when the file is missing."""
        if not self.path.exists():
            return RuntimeSettings()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = f"settings must be a JSON object: {self.path}"
            raise TypeError(msg)
        return RuntimeSettings.model_validate(raw)

    def save(self, settings: RuntimeSettings) -> RuntimeSettings:
        """Persist settings atomically enough for local single-user use."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(settings.model_dump(mode="json", exclude_none=True), indent=2) + "\n",
            encoding="utf-8",
        )
        return settings

    def select_model(
        self,
        *,
        provider: str,
        model_id: str,
        base_url: str | None = None,
    ) -> RuntimeSettings:
        """Persist the selected model for a provider."""
        settings = self.load()
        updates: dict[str, str] = {
            "provider": provider,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if provider == "omlx":
            updates["omlx_model"] = model_id
            if base_url:
                updates["omlx_base_url"] = base_url
        elif provider == "mlx":
            updates["mlx_model"] = model_id
        else:
            updates["provider"] = provider
        return self.save(settings.model_copy(update=updates))


def runtime_settings_path(base_dir: Path) -> Path:
    """Return the default settings path under a MiaOS data dir."""
    return base_dir / "settings.json"


def apply_runtime_settings(settings: RuntimeSettings, *, override: bool = False) -> None:
    """Apply persisted settings to process env for existing provider code paths."""
    values = {
        MIYA_PROVIDER_ENV: settings.provider,
        MIYA_OMLX_BASE_URL_ENV: settings.omlx_base_url,
        MIYA_OMLX_MODEL_ENV: settings.omlx_model,
        MIYA_MLX_MODEL_ENV: settings.mlx_model,
    }
    for key, value in values.items():
        if value and (override or not os.environ.get(key)):
            os.environ[key] = value
