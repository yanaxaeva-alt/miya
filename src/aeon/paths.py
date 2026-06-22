"""Shared AEON data directory resolution."""

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path(".miaos")


def resolve_data_dir(explicit: Path | None = None) -> Path:
    """Resolve MiaOS/AEON state directory (CLI, API, launchd)."""
    if explicit is not None:
        return explicit
    env_value = os.environ.get("MIYA_DATA_DIR")
    if env_value:
        return Path(env_value)
    return DEFAULT_DATA_DIR
