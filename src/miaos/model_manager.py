"""SQLite-backed model registry and ModelManager MVP."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from miaos.runtime import RuntimeCatalog
from miaos.runtime.profiles import ConfigurationError
from miaos.runtime.providers import ModelResolutionError, get_model_providers

DEFAULT_MODEL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / ".miaos" / "model_registry.sqlite3"
)


class LabCertState(StrEnum):
    """Model lab certification state."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


class ModelLifecycleState(StrEnum):
    """Lifecycle states inspired by Block 3."""

    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    REGISTERED = "registered"
    WARMING = "warming"
    RESIDENT = "resident"
    ACTIVE = "active"
    ARCHIVED = "archived"

    @classmethod
    def selectable_states(cls) -> frozenset[ModelLifecycleState]:
        return frozenset(
            {
                cls.DOWNLOADED,
                cls.REGISTERED,
                cls.WARMING,
                cls.RESIDENT,
                cls.ACTIVE,
            }
        )


@dataclass(frozen=True, slots=True)
class ModelRecord:
    """Persisted model metadata."""

    id: str
    provider: str
    family: str
    variant: str
    quantization: str
    context_len: int
    status: ModelLifecycleState
    path: str | None
    pool_role: str | None
    sha256: str | None
    lab_cert: LabCertState | None
    trace_id: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "provider": self.provider,
            "family": self.family,
            "variant": self.variant,
            "quantization": self.quantization,
            "context_len": self.context_len,
            "status": self.status.value,
            "path": self.path,
            "pool_role": self.pool_role,
            "sha256": self.sha256,
            "lab_cert": None if self.lab_cert is None else self.lab_cert.value,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ManagedModelSelection:
    """Resolved registry-backed model selection."""

    trace_id: str
    runtime_profile_name: str
    requested_model_id: str
    selected_record: ModelRecord
    resolution_path: tuple[str, ...]
    used_fallback: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "runtime_profile_name": self.runtime_profile_name,
            "requested_model_id": self.requested_model_id,
            "selected_record": self.selected_record.to_dict(),
            "resolution_path": list(self.resolution_path),
            "used_fallback": self.used_fallback,
            "reason": self.reason,
        }


class DownloadAdapter(Protocol):
    """Deferred interface for future download orchestration."""

    def download(self, source_ref: str, destination: Path, *, trace_id: str) -> Path:
        """Download a model into a local destination."""


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _ensure_trace_id(trace_id: str | None) -> str:
    return trace_id or uuid4().hex


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_local_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Local model path '{resolved}' does not exist or is not a file.")
    return resolved


class ModelManager:
    """MVP model registry manager."""

    def __init__(
        self,
        db_path: Path = DEFAULT_MODEL_REGISTRY_PATH,
        runtime_catalog: RuntimeCatalog | None = None,
    ) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._runtime_catalog = runtime_catalog or RuntimeCatalog.from_directory()
        self._providers = {provider.provider_name(): provider for provider in get_model_providers()}
        self._initialize()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    family TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    quantization TEXT NOT NULL,
                    context_len INTEGER NOT NULL,
                    path TEXT,
                    pool_role TEXT,
                    status TEXT NOT NULL,
                    sha256 TEXT,
                    lab_cert TEXT,
                    trace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS model_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_state TEXT,
                    to_state TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(model_id) REFERENCES models(id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_models_status ON models(status)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_models_lab ON models(lab_cert)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_events_model_id ON model_events(model_id)"
            )

    def register_model(
        self,
        *,
        model_id: str,
        provider: str,
        family: str,
        variant: str,
        quantization: str,
        context_len: int,
        path: str | Path,
        pool_role: str | None = None,
        trace_id: str | None = None,
    ) -> ModelRecord:
        """Register a local model file in the registry."""

        resolved_path = _normalize_local_path(path)
        computed_sha256 = _compute_sha256(resolved_path)
        trace = _ensure_trace_id(trace_id)
        existing = self.get_model(model_id)
        timestamp = _utc_now()

        if existing is not None and existing.status not in {
            ModelLifecycleState.DOWNLOADED,
            ModelLifecycleState.REGISTERED,
        }:
            raise ModelResolutionError(
                f"Cannot register model '{model_id}' from state '{existing.status.value}'."
            )

        with self._connect() as connection:
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO models (
                        id, provider, family, variant, quantization, context_len,
                        path, pool_role, status, sha256, lab_cert, trace_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        provider,
                        family,
                        variant,
                        quantization,
                        context_len,
                        str(resolved_path),
                        pool_role,
                        ModelLifecycleState.REGISTERED.value,
                        computed_sha256,
                        None,
                        trace,
                        timestamp,
                        timestamp,
                    ),
                )
                self._record_event(
                    connection,
                    model_id=model_id,
                    trace_id=trace,
                    event_type="register_model",
                    from_state=None,
                    to_state=ModelLifecycleState.REGISTERED,
                    details={
                        "path": str(resolved_path),
                        "sha256": computed_sha256,
                    },
                )
            else:
                connection.execute(
                    """
                    UPDATE models
                    SET provider = ?,
                        family = ?,
                        variant = ?,
                        quantization = ?,
                        context_len = ?,
                        path = ?,
                        pool_role = ?,
                        status = ?,
                        sha256 = ?,
                        trace_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        provider,
                        family,
                        variant,
                        quantization,
                        context_len,
                        str(resolved_path),
                        pool_role,
                        ModelLifecycleState.REGISTERED.value,
                        computed_sha256,
                        trace,
                        timestamp,
                        model_id,
                    ),
                )
                self._record_event(
                    connection,
                    model_id=model_id,
                    trace_id=trace,
                    event_type="register_model",
                    from_state=existing.status,
                    to_state=ModelLifecycleState.REGISTERED,
                    details={
                        "path": str(resolved_path),
                        "sha256": computed_sha256,
                    },
                )

        record = self.get_model(model_id)
        if record is None:
            raise RuntimeError(f"Failed to persist model '{model_id}'.")
        return record

    def mark_downloaded(
        self,
        *,
        model_id: str,
        provider: str,
        family: str,
        variant: str,
        quantization: str,
        context_len: int,
        path: str | Path,
        pool_role: str | None = None,
        trace_id: str | None = None,
    ) -> ModelRecord:
        """Mark a model as downloaded without requiring full registration lifecycle."""

        resolved_path = _normalize_local_path(path)
        computed_sha256 = _compute_sha256(resolved_path)
        trace = _ensure_trace_id(trace_id)
        existing = self.get_model(model_id)
        timestamp = _utc_now()

        if existing is not None and existing.status not in {
            ModelLifecycleState.DISCOVERED,
            ModelLifecycleState.DOWNLOADED,
        }:
            raise ModelResolutionError(
                f"Cannot mark model '{model_id}' as downloaded from state "
                f"'{existing.status.value}'."
            )

        with self._connect() as connection:
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO models (
                        id, provider, family, variant, quantization, context_len,
                        path, pool_role, status, sha256, lab_cert, trace_id,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        model_id,
                        provider,
                        family,
                        variant,
                        quantization,
                        context_len,
                        str(resolved_path),
                        pool_role,
                        ModelLifecycleState.DOWNLOADED.value,
                        computed_sha256,
                        None,
                        trace,
                        timestamp,
                        timestamp,
                    ),
                )
                self._record_event(
                    connection,
                    model_id=model_id,
                    trace_id=trace,
                    event_type="mark_downloaded",
                    from_state=None,
                    to_state=ModelLifecycleState.DOWNLOADED,
                    details={
                        "path": str(resolved_path),
                        "sha256": computed_sha256,
                    },
                )
            else:
                connection.execute(
                    """
                    UPDATE models
                    SET provider = ?,
                        family = ?,
                        variant = ?,
                        quantization = ?,
                        context_len = ?,
                        path = ?,
                        pool_role = ?,
                        status = ?,
                        sha256 = ?,
                        trace_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        provider,
                        family,
                        variant,
                        quantization,
                        context_len,
                        str(resolved_path),
                        pool_role,
                        ModelLifecycleState.DOWNLOADED.value,
                        computed_sha256,
                        trace,
                        timestamp,
                        model_id,
                    ),
                )
                self._record_event(
                    connection,
                    model_id=model_id,
                    trace_id=trace,
                    event_type="mark_downloaded",
                    from_state=existing.status,
                    to_state=ModelLifecycleState.DOWNLOADED,
                    details={
                        "path": str(resolved_path),
                        "sha256": computed_sha256,
                    },
                )

        record = self.get_model(model_id)
        if record is None:
            raise RuntimeError(f"Failed to persist downloaded model '{model_id}'.")
        return record

    def set_lab_cert(
        self,
        model_id: str,
        lab_cert: LabCertState | str,
        *,
        trace_id: str | None = None,
    ) -> ModelRecord:
        """Update Block 4 lab certification status."""

        existing = self.get_model(model_id)
        if existing is None:
            raise ConfigurationError(f"Unknown model '{model_id}'.")

        cert_value = LabCertState(lab_cert)
        trace = _ensure_trace_id(trace_id)
        timestamp = _utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE models
                SET lab_cert = ?, trace_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (cert_value.value, trace, timestamp, model_id),
            )
            self._record_event(
                connection,
                model_id=model_id,
                trace_id=trace,
                event_type="set_lab_cert",
                from_state=existing.status,
                to_state=existing.status,
                details={"lab_cert": cert_value.value},
            )

        record = self.get_model(model_id)
        if record is None:
            raise RuntimeError(f"Failed to update lab_cert for '{model_id}'.")
        return record

    def list_models(self) -> tuple[ModelRecord, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, provider, family, variant, quantization, context_len,
                       status, path, pool_role, sha256, lab_cert, trace_id,
                       created_at, updated_at
                FROM models
                ORDER BY id
                """
            ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def get_model(self, model_id: str) -> ModelRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, provider, family, variant, quantization, context_len,
                       status, path, pool_role, sha256, lab_cert, trace_id,
                       created_at, updated_at
                FROM models
                WHERE id = ?
                """,
                (model_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_events(self, model_id: str) -> tuple[dict[str, object], ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT model_id, trace_id, event_type, from_state, to_state,
                       details_json, created_at
                FROM model_events
                WHERE model_id = ?
                ORDER BY id
                """,
                (model_id,),
            ).fetchall()
        return tuple(
            {
                "model_id": row["model_id"],
                "trace_id": row["trace_id"],
                "event_type": row["event_type"],
                "from_state": row["from_state"],
                "to_state": row["to_state"],
                "details": json.loads(str(row["details_json"])),
                "created_at": row["created_at"],
            }
            for row in rows
        )

    def select_model_for_profile(
        self,
        runtime_profile_name: str,
        *,
        requested_model_id: str | None = None,
        trace_id: str | None = None,
    ) -> ManagedModelSelection:
        """Select a registered model for a runtime profile with explicit fallback."""

        profile = self._runtime_catalog.get(runtime_profile_name)
        requested = requested_model_id or profile.default_model_id
        trace = _ensure_trace_id(trace_id)
        resolution_path: list[str] = []
        visited: set[str] = set()
        current_model_id = requested
        last_reason = ""

        while True:
            if current_model_id in visited:
                raise ModelResolutionError(
                    f"Fallback cycle detected while selecting for profile '{runtime_profile_name}'."
                )
            visited.add(current_model_id)
            resolution_path.append(current_model_id)

            model_profile = profile.model_by_id(current_model_id)
            provider = self._providers.get(model_profile.provider)
            if provider is None:
                last_reason = f"provider '{model_profile.provider}' is not registered"
            else:
                availability_reason = provider.availability_reason(model_profile, profile.hardware)
                if availability_reason is not None:
                    last_reason = availability_reason
                else:
                    record = self.get_model(model_profile.id)
                    if record is None:
                        last_reason = f"model '{model_profile.id}' is not present in local registry"
                    elif record.status not in ModelLifecycleState.selectable_states():
                        last_reason = (
                            f"model '{model_profile.id}' is in non-selectable state "
                            f"'{record.status.value}'"
                        )
                    elif record.lab_cert == LabCertState.FAILED:
                        last_reason = f"model '{model_profile.id}' has failed lab certification"
                    else:
                        selection = ManagedModelSelection(
                            trace_id=trace,
                            runtime_profile_name=runtime_profile_name,
                            requested_model_id=requested,
                            selected_record=record,
                            resolution_path=tuple(resolution_path),
                            used_fallback=record.id != requested,
                            reason=(
                                "requested-model"
                                if record.id == requested
                                else f"explicit-fallback after {last_reason}"
                            ),
                        )
                        with self._connect() as connection:
                            self._record_event(
                                connection,
                                model_id=record.id,
                                trace_id=trace,
                                event_type="select_model_for_profile",
                                from_state=record.status,
                                to_state=record.status,
                                details=selection.to_dict(),
                            )
                        return selection

            if not model_profile.fallback_ids:
                raise ModelResolutionError(
                    f"Unable to select model '{requested}' for profile '{runtime_profile_name}': "
                    f"{last_reason}. No explicit fallback configured."
                )

            current_model_id = model_profile.fallback_ids[0]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ModelRecord:
        lab_cert_raw = row["lab_cert"]
        return ModelRecord(
            id=str(row["id"]),
            provider=str(row["provider"]),
            family=str(row["family"]),
            variant=str(row["variant"]),
            quantization=str(row["quantization"]),
            context_len=int(row["context_len"]),
            status=ModelLifecycleState(str(row["status"])),
            path=None if row["path"] is None else str(row["path"]),
            pool_role=None if row["pool_role"] is None else str(row["pool_role"]),
            sha256=None if row["sha256"] is None else str(row["sha256"]),
            lab_cert=None if lab_cert_raw is None else LabCertState(str(lab_cert_raw)),
            trace_id=str(row["trace_id"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _record_event(
        connection: sqlite3.Connection,
        *,
        model_id: str,
        trace_id: str,
        event_type: str,
        from_state: ModelLifecycleState | None,
        to_state: ModelLifecycleState | None,
        details: dict[str, object],
    ) -> None:
        connection.execute(
            """
            INSERT INTO model_events (
                model_id, trace_id, event_type, from_state, to_state, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                trace_id,
                event_type,
                None if from_state is None else from_state.value,
                None if to_state is None else to_state.value,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                _utc_now(),
            ),
        )
