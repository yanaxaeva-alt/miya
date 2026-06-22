"""Persist AEON heartbeat ticks for status and editor probes."""

import json
from pathlib import Path
from typing import Any


def ticks_path(base_dir: Path) -> Path:
    return base_dir / "aeon_ticks.jsonl"


def append_tick(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_recent_ticks(path: Path, *, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    recent: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        recent.append(json.loads(line))
    return recent
