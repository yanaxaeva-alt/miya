"""Persist AEON goal pool to disk."""

import json
from pathlib import Path

from aeon.types import Goal


def goals_path(base_dir: Path) -> Path:
    return base_dir / "aeon_goals.json"


def load_goals(path: Path) -> list[Goal]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = f"Goal store must be a JSON list: {path}"
        raise ValueError(msg)
    return [Goal.model_validate(item) for item in raw]


def save_goals(path: Path, goals: list[Goal]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [goal.model_dump(mode="json") for goal in goals]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
