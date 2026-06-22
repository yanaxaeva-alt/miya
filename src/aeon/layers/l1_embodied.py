"""Layer 1 — Embodied Interface."""

import os
import socket
from datetime import UTC, datetime
from pathlib import Path

from aeon.types import WorldSnapshot


class EmbodiedInterface:
    """Read-only macOS-facing sensors and guarded effector hooks."""

    def __init__(
        self,
        *,
        readonly: bool = True,
        watch_dir: Path | None = None,
        extra_watch_dirs: list[Path] | None = None,
    ) -> None:
        self.readonly = readonly
        self.watch_dir = watch_dir or Path.cwd()
        self.extra_watch_dirs = extra_watch_dirs or []

    def snapshot(self) -> WorldSnapshot:
        """Capture a lightweight world snapshot."""
        recent_files = self._recent_files(self.watch_dir, limit=8)
        for extra_dir in self.extra_watch_dirs:
            label = extra_dir.name or str(extra_dir)
            for relative in self._recent_files(extra_dir, limit=4):
                recent_files.append(f"{label}:{relative}")
        recent_files = recent_files[:12]
        return WorldSnapshot(
            timestamp=datetime.now(tz=UTC).isoformat(),
            cwd=str(self.watch_dir.resolve()),
            hostname=socket.gethostname(),
            recent_files=recent_files,
            process_count=os.cpu_count() or 1,
        )

    def read_text_file(self, relative_path: str) -> str:
        """Read one file under the watch directory."""
        target = (self.watch_dir / relative_path).resolve()
        root = self.watch_dir.resolve()
        if root not in target.parents and target != root:
            msg = f"Path escapes embodied watch dir: {relative_path}"
            raise ValueError(msg)
        return target.read_text(encoding="utf-8")

    @staticmethod
    def _recent_files(root: Path, *, limit: int) -> list[str]:
        if not root.exists():
            return []
        candidates: list[tuple[float, str]] = []
        for path in root.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                try:
                    candidates.append((path.stat().st_mtime, str(path.relative_to(root))))
                except OSError:
                    continue
        candidates.sort(reverse=True)
        return [name for _, name in candidates[:limit]]
