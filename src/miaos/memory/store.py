"""SQLite-backed MVP memory store with audited mutations."""

import json
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from miaos.observability import DecisionLog, DecisionLogEvent
from miaos.safety import ActionClass, ActionRequest, PolicyDecision, PolicyDecisionType, PolicyGate


def _memory_id(prefix: str) -> str:
    """Generate a stable memory identifier."""
    return f"{prefix}_{uuid4().hex}"


def _now() -> datetime:
    """Return current UTC time."""
    return datetime.now(UTC)


class MemoryStoreError(RuntimeError):
    """Base error for memory store operations."""


class MemoryNotFoundError(MemoryStoreError):
    """Raised when a requested memory record does not exist."""


class MemoryKind(StrEnum):
    """MVP long-term memory record kinds."""

    EPISODIC = "episodic"
    USER_FACT = "user_fact"
    DOMAIN_NOTE = "domain_note"


class MemoryRecord(BaseModel):
    """Common view over memory records."""

    id: str
    kind: MemoryKind
    content: str
    semantic_tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, str | float] = Field(default_factory=dict)


class EpisodicMemory(BaseModel):
    """One episodic memory entry."""

    id: str = Field(default_factory=lambda: _memory_id("episode"))
    content: str = Field(min_length=1)
    summary: str | None = None
    semantic_tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.0, ge=0.0, le=10.0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UserProfileFact(BaseModel):
    """One fact remembered about the user."""

    id: str = Field(default_factory=lambda: _memory_id("fact"))
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    semantic_tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class DomainNote(BaseModel):
    """One domain-specific note."""

    id: str = Field(default_factory=lambda: _memory_id("note"))
    domain: str = Field(min_length=1)
    note: str = Field(min_length=1)
    semantic_tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class MemoryDeletionResult(BaseModel):
    """Result of an audited memory deletion attempt."""

    memory_id: str
    kind: MemoryKind
    deleted: bool
    decision: PolicyDecision
    approved_by: str | None = None


class MemoryStore:
    """SQLite memory store for episodic memories, user facts, and domain notes."""

    def __init__(
        self,
        *,
        db_path: Path,
        decision_log: DecisionLog,
        policy_gate: PolicyGate | None = None,
    ) -> None:
        """Create and initialize a memory store."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.decision_log = decision_log
        self.policy_gate = policy_gate or PolicyGate()
        self.initialize()

    def initialize(self) -> None:
        """Create memory tables if needed."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    summary TEXT,
                    semantic_tags_json TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_facts (
                    id TEXT PRIMARY KEY,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    semantic_tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_user_facts_key ON user_facts(key)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS domain_notes (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    note TEXT NOT NULL,
                    semantic_tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_domain_notes_domain ON domain_notes(domain)"
            )

    def add_episode(
        self,
        *,
        content: str,
        summary: str | None = None,
        semantic_tags: list[str] | None = None,
        importance: float = 0.0,
        actor: str = "mia.memory",
    ) -> EpisodicMemory:
        """Add an episodic memory after write authorization."""
        record = EpisodicMemory(
            content=content,
            summary=summary,
            semantic_tags=semantic_tags or [],
            importance=importance,
        )
        self._authorize_write(actor=actor, resource=f"memory://{MemoryKind.EPISODIC}/{record.id}")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO episodes
                    (id, content, summary, semantic_tags_json, importance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._episode_values(record),
            )
        self._append_memory_event("memory_upserted", record.id, MemoryKind.EPISODIC)
        return record

    def get_episode(self, memory_id: str) -> EpisodicMemory:
        """Return one episodic memory."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM episodes WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            raise MemoryNotFoundError(memory_id)
        return self._row_to_episode(row)

    def list_episodes(self, *, tag: str | None = None) -> list[EpisodicMemory]:
        """List episodic memories, optionally filtered by semantic tag."""
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM episodes ORDER BY created_at, id").fetchall()
        records = [self._row_to_episode(row) for row in rows]
        if tag is None:
            return records
        return [record for record in records if tag in record.semantic_tags]

    def update_episode(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        summary: str | None = None,
        semantic_tags: list[str] | None = None,
        importance: float | None = None,
    ) -> EpisodicMemory:
        """Update an episodic memory after write authorization."""
        current = self.get_episode(memory_id)
        updated = current.model_copy(
            update={
                "content": content if content is not None else current.content,
                "summary": summary if summary is not None else current.summary,
                "semantic_tags": semantic_tags
                if semantic_tags is not None
                else current.semantic_tags,
                "importance": importance if importance is not None else current.importance,
                "updated_at": _now(),
            }
        )
        self._authorize_write(
            actor="mia.memory",
            resource=f"memory://{MemoryKind.EPISODIC}/{memory_id}",
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE episodes
                SET content = ?, summary = ?, semantic_tags_json = ?, importance = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.content,
                    updated.summary,
                    self._tags_json(updated.semantic_tags),
                    updated.importance,
                    updated.updated_at.isoformat(),
                    memory_id,
                ),
            )
        self._append_memory_event("memory_upserted", memory_id, MemoryKind.EPISODIC)
        return self.get_episode(memory_id)

    def add_user_fact(
        self,
        *,
        key: str,
        value: str,
        confidence: float = 1.0,
        semantic_tags: list[str] | None = None,
        actor: str = "mia.memory",
    ) -> UserProfileFact:
        """Add a user-profile fact after write authorization."""
        record = UserProfileFact(
            key=key,
            value=value,
            confidence=confidence,
            semantic_tags=semantic_tags or [],
        )
        self._authorize_write(actor=actor, resource=f"memory://{MemoryKind.USER_FACT}/{record.id}")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_facts
                    (id, key, value, confidence, semantic_tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                self._user_fact_values(record),
            )
        self._append_memory_event("memory_upserted", record.id, MemoryKind.USER_FACT)
        return record

    def get_user_fact(self, memory_id: str) -> UserProfileFact:
        """Return one user fact."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_facts WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(memory_id)
        return self._row_to_user_fact(row)

    def list_user_facts(self, *, tag: str | None = None) -> list[UserProfileFact]:
        """List user facts, optionally filtered by semantic tag."""
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM user_facts ORDER BY created_at, id").fetchall()
        records = [self._row_to_user_fact(row) for row in rows]
        if tag is None:
            return records
        return [record for record in records if tag in record.semantic_tags]

    def update_user_fact(
        self,
        memory_id: str,
        *,
        value: str | None = None,
        confidence: float | None = None,
        semantic_tags: list[str] | None = None,
        actor: str = "mia.memory",
    ) -> UserProfileFact:
        """Update a user fact after write authorization."""
        current = self.get_user_fact(memory_id)
        updated = current.model_copy(
            update={
                "value": value if value is not None else current.value,
                "confidence": confidence if confidence is not None else current.confidence,
                "semantic_tags": semantic_tags
                if semantic_tags is not None
                else current.semantic_tags,
                "updated_at": _now(),
            }
        )
        self._authorize_write(actor=actor, resource=f"memory://{MemoryKind.USER_FACT}/{memory_id}")
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE user_facts
                SET value = ?, confidence = ?, semantic_tags_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.value,
                    updated.confidence,
                    self._tags_json(updated.semantic_tags),
                    updated.updated_at.isoformat(),
                    memory_id,
                ),
            )
        self._append_memory_event("memory_upserted", memory_id, MemoryKind.USER_FACT)
        return self.get_user_fact(memory_id)

    def add_domain_note(
        self,
        *,
        domain: str,
        note: str,
        semantic_tags: list[str] | None = None,
        actor: str = "mia.memory",
    ) -> DomainNote:
        """Add a domain note after write authorization."""
        record = DomainNote(domain=domain, note=note, semantic_tags=semantic_tags or [])
        self._authorize_write(actor=actor, resource=f"memory://{MemoryKind.DOMAIN_NOTE}/{record.id}")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO domain_notes
                    (id, domain, note, semantic_tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._domain_note_values(record),
            )
        self._append_memory_event("memory_upserted", record.id, MemoryKind.DOMAIN_NOTE)
        return record

    def get_domain_note(self, memory_id: str) -> DomainNote:
        """Return one domain note."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM domain_notes WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            raise MemoryNotFoundError(memory_id)
        return self._row_to_domain_note(row)

    def list_domain_notes(
        self,
        *,
        domain: str | None = None,
        tag: str | None = None,
    ) -> list[DomainNote]:
        """List domain notes, optionally filtered by domain and semantic tag."""
        with self._connect() as connection:
            if domain is None:
                rows = connection.execute(
                    "SELECT * FROM domain_notes ORDER BY created_at, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM domain_notes WHERE domain = ? ORDER BY created_at, id",
                    (domain,),
                ).fetchall()
        records = [self._row_to_domain_note(row) for row in rows]
        if tag is None:
            return records
        return [record for record in records if tag in record.semantic_tags]

    def update_domain_note(
        self,
        memory_id: str,
        *,
        note: str | None = None,
        semantic_tags: list[str] | None = None,
        actor: str = "mia.memory",
    ) -> DomainNote:
        """Update a domain note after write authorization."""
        current = self.get_domain_note(memory_id)
        updated = current.model_copy(
            update={
                "note": note if note is not None else current.note,
                "semantic_tags": semantic_tags
                if semantic_tags is not None
                else current.semantic_tags,
                "updated_at": _now(),
            }
        )
        self._authorize_write(
            actor=actor,
            resource=f"memory://{MemoryKind.DOMAIN_NOTE}/{memory_id}",
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE domain_notes
                SET note = ?, semantic_tags_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.note,
                    self._tags_json(updated.semantic_tags),
                    updated.updated_at.isoformat(),
                    memory_id,
                ),
            )
        self._append_memory_event("memory_upserted", memory_id, MemoryKind.DOMAIN_NOTE)
        return self.get_domain_note(memory_id)

    def delete_memory(
        self,
        kind: MemoryKind,
        memory_id: str,
        *,
        actor: str = "mia.memory",
        approved_by: str | None = None,
    ) -> MemoryDeletionResult:
        """Delete a memory record only after policy evaluation and explicit approval."""
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=ActionClass.DELETE,
                actor=actor,
                resource=f"memory://{kind}/{memory_id}",
                description=f"delete memory: {kind.value}",
            )
        )
        self.decision_log.append_policy_decision(decision)

        if decision.decision == PolicyDecisionType.DENY:
            return MemoryDeletionResult(
                memory_id=memory_id,
                kind=kind,
                deleted=False,
                decision=decision,
            )

        if decision.decision == PolicyDecisionType.REQUIRE_APPROVAL and approved_by is None:
            return MemoryDeletionResult(
                memory_id=memory_id,
                kind=kind,
                deleted=False,
                decision=decision,
            )

        if approved_by is not None:
            self.decision_log.append(
                DecisionLogEvent(
                    event_type="memory_delete_approved",
                    trace_id=decision.trace_id,
                    summary=f"{kind.value} deletion approved",
                    actor=approved_by,
                    refs={"memory_id": memory_id, "kind": kind.value},
                )
            )

        deleted = self._delete_row(kind, memory_id)
        self.decision_log.append(
            DecisionLogEvent(
                event_type="memory_deleted",
                trace_id=decision.trace_id,
                summary=f"{kind.value} deleted: {deleted}",
                actor="memory_store",
                refs={
                    "memory_id": memory_id,
                    "kind": kind.value,
                    "deleted": str(deleted).lower(),
                },
            )
        )
        return MemoryDeletionResult(
            memory_id=memory_id,
            kind=kind,
            deleted=deleted,
            decision=decision,
            approved_by=approved_by,
        )

    def to_memory_record(
        self,
        record: EpisodicMemory | UserProfileFact | DomainNote,
    ) -> MemoryRecord:
        """Return a common memory record view."""
        if isinstance(record, EpisodicMemory):
            return MemoryRecord(
                id=record.id,
                kind=MemoryKind.EPISODIC,
                content=record.content,
                semantic_tags=record.semantic_tags,
                created_at=record.created_at,
                updated_at=record.updated_at,
                metadata={"importance": record.importance},
            )
        if isinstance(record, UserProfileFact):
            return MemoryRecord(
                id=record.id,
                kind=MemoryKind.USER_FACT,
                content=f"{record.key}: {record.value}",
                semantic_tags=record.semantic_tags,
                created_at=record.created_at,
                updated_at=record.updated_at,
                metadata={"key": record.key, "confidence": record.confidence},
            )
        return MemoryRecord(
            id=record.id,
            kind=MemoryKind.DOMAIN_NOTE,
            content=record.note,
            semantic_tags=record.semantic_tags,
            created_at=record.created_at,
            updated_at=record.updated_at,
            metadata={"domain": record.domain},
        )

    def _authorize_write(self, *, actor: str, resource: str) -> None:
        """Evaluate and log a sandbox-write policy decision."""
        decision = self.policy_gate.evaluate(
            ActionRequest(
                action_class=ActionClass.SANDBOX_WRITE,
                actor=actor,
                resource=resource,
                description="memory write",
            )
        )
        self.decision_log.append_policy_decision(decision)
        if decision.decision != PolicyDecisionType.ALLOW:
            msg = f"memory write blocked: {decision.reason}"
            raise MemoryStoreError(msg)

    def _append_memory_event(self, event_type: str, memory_id: str, kind: MemoryKind) -> None:
        """Append a memory mutation audit event."""
        self.decision_log.append(
            DecisionLogEvent(
                event_type=event_type,
                trace_id=f"memory_{memory_id}",
                summary=f"{kind.value} {event_type}",
                actor="memory_store",
                refs={"memory_id": memory_id, "kind": kind.value},
            )
        )

    def _delete_row(self, kind: MemoryKind, memory_id: str) -> bool:
        """Delete one row and return whether it existed."""
        statement = {
            MemoryKind.EPISODIC: "DELETE FROM episodes WHERE id = ?",
            MemoryKind.USER_FACT: "DELETE FROM user_facts WHERE id = ?",
            MemoryKind.DOMAIN_NOTE: "DELETE FROM domain_notes WHERE id = ?",
        }[kind]
        with self._connect() as connection:
            cursor = connection.execute(statement, (memory_id,))
        return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row mappings."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _episode_values(record: EpisodicMemory) -> tuple[object, ...]:
        """Serialize an episode for SQLite."""
        return (
            record.id,
            record.content,
            record.summary,
            MemoryStore._tags_json(record.semantic_tags),
            record.importance,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    @staticmethod
    def _user_fact_values(record: UserProfileFact) -> tuple[object, ...]:
        """Serialize a user fact for SQLite."""
        return (
            record.id,
            record.key,
            record.value,
            record.confidence,
            MemoryStore._tags_json(record.semantic_tags),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    @staticmethod
    def _domain_note_values(record: DomainNote) -> tuple[object, ...]:
        """Serialize a domain note for SQLite."""
        return (
            record.id,
            record.domain,
            record.note,
            MemoryStore._tags_json(record.semantic_tags),
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    @staticmethod
    def _row_to_episode(row: sqlite3.Row) -> EpisodicMemory:
        """Deserialize an episode row."""
        return EpisodicMemory(
            id=str(row["id"]),
            content=str(row["content"]),
            summary=row["summary"],
            semantic_tags=MemoryStore._tags_from_json(str(row["semantic_tags_json"])),
            importance=float(row["importance"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    @staticmethod
    def _row_to_user_fact(row: sqlite3.Row) -> UserProfileFact:
        """Deserialize a user fact row."""
        return UserProfileFact(
            id=str(row["id"]),
            key=str(row["key"]),
            value=str(row["value"]),
            confidence=float(row["confidence"]),
            semantic_tags=MemoryStore._tags_from_json(str(row["semantic_tags_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    @staticmethod
    def _row_to_domain_note(row: sqlite3.Row) -> DomainNote:
        """Deserialize a domain note row."""
        return DomainNote(
            id=str(row["id"]),
            domain=str(row["domain"]),
            note=str(row["note"]),
            semantic_tags=MemoryStore._tags_from_json(str(row["semantic_tags_json"])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    @staticmethod
    def _tags_json(tags: list[str]) -> str:
        """Serialize semantic tags."""
        return json.dumps(tags, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _tags_from_json(raw: str) -> list[str]:
        """Deserialize semantic tags."""
        decoded = json.loads(raw)
        if not isinstance(decoded, list):
            msg = "semantic_tags_json must contain a list"
            raise MemoryStoreError(msg)
        return [str(tag) for tag in decoded]
