"""Tests for SQLite memory store."""

from pathlib import Path

from miaos.memory import MemoryStore


def test_memory_store_episodes_profile_notes_and_deletions(tmp_path: Path) -> None:
    """Memory store persists episodes, profile facts, notes, and deletion logs."""
    store = MemoryStore(tmp_path / "memory.sqlite3")

    episode = store.add_episode(
        package_id="mia",
        role="user",
        content="hello Mia",
        tags=["chat"],
    )
    fact = store.upsert_profile_fact(package_id="mia", key="locale", value="ru-RU")
    note = store.add_domain_note(
        package_id="mia",
        domain="philosophy",
        content="Prefers concise answers.",
        tags=["style"],
    )

    assert len(store.list_episodes("mia")) == 1
    assert store.list_profile_facts("mia")[0].key == "locale"
    assert store.list_domain_notes("mia", domain="philosophy")[0].id == note.id

    assert store.delete_episode(episode.id, "mia") is True
    assert store.delete_domain_note(note.id, "mia") is True

    summary = store.summary("mia")
    assert summary["episodes"] == 0
    assert summary["profile_facts"] == 1
    assert summary["domain_notes"] == 0
    assert summary["deletions_logged"] == 2
    assert fact.value == "ru-RU"
