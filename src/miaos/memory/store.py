"""SQLite-backed episodic memory, profile facts, and domain notes."""

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class MemoryEpisode(BaseModel):
    """One episodic memory record."""

    id: str
    package_id: str
    trace_id: str | None = None
    role: str = "assistant"
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: str


class ProfileFact(BaseModel):
    """User profile fact scoped to a persona package."""

    id: str
    package_id: str
    key: str
    value: str
    created_at: str
    updated_at: str


class DomainNote(BaseModel):
    """Domain-scoped note for a persona package."""

    id: str
    package_id: str
    domain: str
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: str


class MemoryDeletionLogEntry(BaseModel):
    """Audit entry for memory deletions."""

    id: str
    package_id: str
    record_type: str
    record_id: str
    deleted_at: str


class MemoryStore:
    """Persist memory MVP data in SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_episodes (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    trace_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memory_episodes_pkg
                    ON memory_episodes(package_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS profile_facts (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(package_id, fact_key)
                );

                CREATE TABLE IF NOT EXISTS domain_notes (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_domain_notes_pkg
                    ON domain_notes(package_id, domain, created_at DESC);

                CREATE TABLE IF NOT EXISTS memory_deletions (
                    id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    deleted_at TEXT NOT NULL
                );
                """
            )

    def add_episode(
        self,
        *,
        package_id: str,
        content: str,
        role: str = "assistant",
        trace_id: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEpisode:
        episode = MemoryEpisode(
            id=str(uuid.uuid4()),
            package_id=package_id,
            trace_id=trace_id,
            role=role,
            content=content,
            tags=tags or [],
            created_at=_now_iso(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_episodes
                    (id, package_id, trace_id, role, content, tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode.id,
                    episode.package_id,
                    episode.trace_id,
                    episode.role,
                    episode.content,
                    json.dumps(episode.tags),
                    episode.created_at,
                ),
            )
        return episode

    def list_episodes(self, package_id: str, limit: int = 50) -> list[MemoryEpisode]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, package_id, trace_id, role, content, tags_json, created_at
                FROM memory_episodes
                WHERE package_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (package_id, limit),
            ).fetchall()
        return [_row_to_episode(row) for row in rows]

    def delete_episode(self, episode_id: str, package_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memory_episodes WHERE id = ? AND package_id = ?",
                (episode_id, package_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                self._log_deletion(connection, package_id, "episode", episode_id)
        return deleted

    def upsert_profile_fact(self, *, package_id: str, key: str, value: str) -> ProfileFact:
        now = _now_iso()
        fact_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profile_facts (
                    id, package_id, fact_key, fact_value, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id, fact_key) DO UPDATE SET
                    fact_value = excluded.fact_value,
                    updated_at = excluded.updated_at
                """,
                (fact_id, package_id, key, value, now, now),
            )
            row = connection.execute(
                """
                SELECT id, package_id, fact_key, fact_value, created_at, updated_at
                FROM profile_facts
                WHERE package_id = ? AND fact_key = ?
                """,
                (package_id, key),
            ).fetchone()
        assert row is not None
        return ProfileFact(
            id=row[0],
            package_id=row[1],
            key=row[2],
            value=row[3],
            created_at=row[4],
            updated_at=row[5],
        )

    def list_profile_facts(self, package_id: str) -> list[ProfileFact]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, package_id, fact_key, fact_value, created_at, updated_at
                FROM profile_facts
                WHERE package_id = ?
                ORDER BY fact_key
                """,
                (package_id,),
            ).fetchall()
        return [
            ProfileFact(
                id=row[0],
                package_id=row[1],
                key=row[2],
                value=row[3],
                created_at=row[4],
                updated_at=row[5],
            )
            for row in rows
        ]

    def add_domain_note(
        self,
        *,
        package_id: str,
        domain: str,
        content: str,
        tags: list[str] | None = None,
    ) -> DomainNote:
        note = DomainNote(
            id=str(uuid.uuid4()),
            package_id=package_id,
            domain=domain,
            content=content,
            tags=tags or [],
            created_at=_now_iso(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO domain_notes
                    (id, package_id, domain, content, tags_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    note.id,
                    note.package_id,
                    note.domain,
                    note.content,
                    json.dumps(note.tags),
                    note.created_at,
                ),
            )
        return note

    def list_domain_notes(self, package_id: str, domain: str | None = None) -> list[DomainNote]:
        query = """
            SELECT id, package_id, domain, content, tags_json, created_at
            FROM domain_notes
            WHERE package_id = ?
        """
        params: list[object] = [package_id]
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_note(row) for row in rows]

    def delete_domain_note(self, note_id: str, package_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM domain_notes WHERE id = ? AND package_id = ?",
                (note_id, package_id),
            )
            deleted = cursor.rowcount > 0
            if deleted:
                self._log_deletion(connection, package_id, "domain_note", note_id)
        return deleted

    def summary(self, package_id: str) -> dict[str, int]:
        with self._connect() as connection:
            episodes = connection.execute(
                "SELECT COUNT(*) FROM memory_episodes WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0]
            facts = connection.execute(
                "SELECT COUNT(*) FROM profile_facts WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0]
            notes = connection.execute(
                "SELECT COUNT(*) FROM domain_notes WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0]
            deletions = connection.execute(
                "SELECT COUNT(*) FROM memory_deletions WHERE package_id = ?",
                (package_id,),
            ).fetchone()[0]
        return {
            "episodes": episodes,
            "profile_facts": facts,
            "domain_notes": notes,
            "deletions_logged": deletions,
        }

    def _log_deletion(
        self,
        connection: sqlite3.Connection,
        package_id: str,
        record_type: str,
        record_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_deletions (id, package_id, record_type, record_id, deleted_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), package_id, record_type, record_id, _now_iso()),
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_episode(row: tuple[object, ...]) -> MemoryEpisode:
    return MemoryEpisode(
        id=str(row[0]),
        package_id=str(row[1]),
        trace_id=str(row[2]) if row[2] else None,
        role=str(row[3]),
        content=str(row[4]),
        tags=json.loads(str(row[5])),
        created_at=str(row[6]),
    )


def _row_to_note(row: tuple[object, ...]) -> DomainNote:
    return DomainNote(
        id=str(row[0]),
        package_id=str(row[1]),
        domain=str(row[2]),
        content=str(row[3]),
        tags=json.loads(str(row[4])),
        created_at=str(row[5]),
    )
