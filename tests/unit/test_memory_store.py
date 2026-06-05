"""Tests for SQLite-backed memory MVP."""

from pathlib import Path

import pytest

from miaos.memory import MemoryKind, MemoryNotFoundError, MemoryStore
from miaos.observability import DecisionLog
from miaos.safety import PolicyDecisionType

UPDATED_CONFIDENCE = 0.95


def _store(tmp_path: Path) -> tuple[MemoryStore, DecisionLog]:
    """Create an isolated memory store and decision log."""
    log = DecisionLog(tmp_path / "decisions.jsonl")
    return MemoryStore(db_path=tmp_path / "memory.sqlite3", decision_log=log), log


def test_episodic_memory_crud_with_semantic_tags(tmp_path: Path) -> None:
    """Episodes can be created, listed by tag, read, and updated."""
    store, log = _store(tmp_path)

    created = store.add_episode(
        content="User discussed local MLX inference.",
        summary="MLX discussion",
        semantic_tags=["mlx", "runtime"],
        importance=6.5,
    )
    updated = store.update_episode(
        created.id,
        summary="Updated MLX discussion",
        semantic_tags=["mlx", "memory"],
    )

    assert store.get_episode(created.id).summary == "Updated MLX discussion"
    assert updated.semantic_tags == ["mlx", "memory"]
    assert [episode.id for episode in store.list_episodes(tag="memory")] == [created.id]
    assert log.verify_integrity() is True


def test_user_profile_fact_crud_with_tags(tmp_path: Path) -> None:
    """User facts support create, list, read, and update."""
    store, _log = _store(tmp_path)

    fact = store.add_user_fact(
        key="preferred_locale",
        value="ru-RU",
        confidence=0.9,
        semantic_tags=["profile", "locale"],
    )
    updated = store.update_user_fact(
        fact.id,
        value="ru",
        confidence=UPDATED_CONFIDENCE,
        semantic_tags=["profile"],
    )

    assert updated.value == "ru"
    assert updated.confidence == UPDATED_CONFIDENCE
    assert store.get_user_fact(fact.id).key == "preferred_locale"
    assert [record.id for record in store.list_user_facts(tag="profile")] == [fact.id]


def test_domain_note_crud_with_domain_and_tag_filters(tmp_path: Path) -> None:
    """Domain notes support create, list filters, read, and update."""
    store, _log = _store(tmp_path)

    note = store.add_domain_note(
        domain="blogging",
        note="Draft before publishing.",
        semantic_tags=["safety", "draft"],
    )
    store.add_domain_note(domain="coding", note="Run tests.", semantic_tags=["quality"])
    updated = store.update_domain_note(
        note.id,
        note="Draft before publishing and require approval for publish.",
        semantic_tags=["safety"],
    )

    assert updated.note.endswith("approval for publish.")
    assert [record.id for record in store.list_domain_notes(domain="blogging")] == [note.id]
    assert [record.id for record in store.list_domain_notes(tag="safety")] == [note.id]


def test_memory_deletion_without_approval_is_logged_and_blocked(tmp_path: Path) -> None:
    """Deletion requires approval and preserves the record without it."""
    store, log = _store(tmp_path)
    episode = store.add_episode(content="Important memory", semantic_tags=["keep"])

    result = store.delete_memory(MemoryKind.EPISODIC, episode.id)

    assert result.deleted is False
    assert result.decision.decision == PolicyDecisionType.REQUIRE_APPROVAL
    assert store.get_episode(episode.id).content == "Important memory"
    assert log.verify_integrity() is True
    assert "delete -> require_approval" in [
        event.summary for event in log.list_events() if event.event_type == "policy_decision"
    ]


def test_memory_deletion_with_approval_removes_record_and_audits(tmp_path: Path) -> None:
    """Explicit approval permits deletion and records the audit trail."""
    store, log = _store(tmp_path)
    fact = store.add_user_fact(key="timezone", value="UTC", semantic_tags=["profile"])

    result = store.delete_memory(
        MemoryKind.USER_FACT,
        fact.id,
        approved_by="human.owner",
    )

    assert result.deleted is True
    assert result.approved_by == "human.owner"
    with pytest.raises(MemoryNotFoundError):
        store.get_user_fact(fact.id)
    assert [event.event_type for event in log.list_events()][-3:] == [
        "policy_decision",
        "memory_delete_approved",
        "memory_deleted",
    ]
    assert log.verify_integrity() is True
