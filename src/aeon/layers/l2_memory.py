"""Layer 2 — Substrate Memory."""

from pathlib import Path

from miaos.memory import MemoryStore

from aeon.types import Goal


class SubstrateMemory:
    """Wrap MiaOS memory store and lightweight skill notes."""

    def __init__(self, store: MemoryStore, *, package_id: str) -> None:
        self.store = store
        self.package_id = package_id

    def remember_episode(
        self,
        *,
        trace_id: str,
        role: str,
        content: str,
        tags: list[str] | None = None,
    ) -> None:
        """Persist one episodic record."""
        self.store.add_episode(
            package_id=self.package_id,
            trace_id=trace_id,
            role=role,
            content=content,
            tags=tags or [],
        )

    def recent_episodes(self, *, limit: int = 5) -> list[str]:
        """Return recent episode summaries for context assembly."""
        episodes = self.store.list_episodes(self.package_id, limit=limit)
        return [f"{episode.role}: {episode.content}" for episode in episodes]

    def remember_skill(self, *, name: str, content: str, domain: str = "aeon") -> None:
        """Store a distilled workflow note."""
        self.store.add_domain_note(
            package_id=self.package_id,
            domain=domain,
            content=f"{name}: {content}",
            tags=["skill", name],
        )

    def skill_hints(self, *, limit: int = 5) -> list[str]:
        """Return recent skill notes."""
        notes = self.store.list_domain_notes(self.package_id, domain="aeon")
        return [note.content for note in notes[:limit]]

    def consolidate_goal_progress(self, goal: Goal, *, delta: float) -> Goal:
        """Update goal progress and return the updated goal."""
        updated = goal.model_copy(update={"progress": min(1.0, goal.progress + delta)})
        return updated

    @staticmethod
    def default_db_path(base_dir: Path) -> Path:
        return base_dir / "memory.sqlite3"
