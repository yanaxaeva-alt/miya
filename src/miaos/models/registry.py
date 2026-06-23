"""SQLite-backed model registry."""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from miaos.models.records import LabCertificationStatus, ModelLifecycleState, ModelRecord


class ModelRegistryError(RuntimeError):
    """Base error for model registry operations."""


class ModelNotFoundError(ModelRegistryError):
    """Raised when a requested model record does not exist."""


MODEL_COLUMNS = (
    "id",
    "repo",
    "family",
    "params_billion",
    "active_params_billion",
    "is_moe",
    "quant",
    "size_bytes",
    "context_len",
    "path",
    "pool_role",
    "status",
    "tok_per_sec",
    "checksum_sha256",
    "added_at",
    "last_used",
    "lab_cert",
    "notes",
)
MODEL_COLUMNS_SQL = ", ".join(MODEL_COLUMNS)
MODEL_PLACEHOLDERS_SQL = ", ".join("?" for _ in MODEL_COLUMNS)
INSERT_MODEL_SQL = f"INSERT INTO models ({MODEL_COLUMNS_SQL}) VALUES ({MODEL_PLACEHOLDERS_SQL})"
SELECT_MODELS_SQL = f"SELECT {MODEL_COLUMNS_SQL} FROM models ORDER BY added_at, id"
SELECT_MODEL_SQL = f"SELECT {MODEL_COLUMNS_SQL} FROM models WHERE id = ?"


class ModelRegistry:
    """SQLite model registry."""

    def __init__(self, db_path: Path) -> None:
        """Create a registry and initialize its schema."""
        self.db_path = db_path
        self.initialize()

    def initialize(self) -> None:
        """Create model registry tables if needed."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    repo TEXT NOT NULL,
                    family TEXT NOT NULL,
                    params_billion REAL NOT NULL,
                    active_params_billion REAL,
                    is_moe INTEGER NOT NULL DEFAULT 0,
                    quant TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    context_len INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    pool_role TEXT,
                    status TEXT NOT NULL,
                    tok_per_sec REAL,
                    checksum_sha256 TEXT,
                    added_at TEXT NOT NULL,
                    last_used TEXT,
                    lab_cert TEXT,
                    notes TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_models_status ON models(status)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_models_role ON models(pool_role, is_moe)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_models_lab ON models(lab_cert)")

    def register(self, record: ModelRecord) -> ModelRecord:
        """Insert a model record."""
        values = self._record_values(record)
        with self._connect() as connection:
            connection.execute(
                INSERT_MODEL_SQL,
                values,
            )
        return record

    def list(self) -> list[ModelRecord]:
        """Return all model records ordered by insertion time."""
        with self._connect() as connection:
            rows = connection.execute(SELECT_MODELS_SQL).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get(self, model_id: str) -> ModelRecord:
        """Return a model record by id."""
        with self._connect() as connection:
            row = connection.execute(
                SELECT_MODEL_SQL,
                (model_id,),
            ).fetchone()
        if row is None:
            raise ModelNotFoundError(model_id)
        return self._row_to_record(row)

    def update_status(self, model_id: str, status: ModelLifecycleState) -> ModelRecord:
        """Update a model lifecycle state."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE models SET status = ? WHERE id = ?",
                (status.value, model_id),
            )
        if cursor.rowcount == 0:
            raise ModelNotFoundError(model_id)
        return self.get(model_id)

    def set_lab_cert(
        self,
        model_id: str,
        lab_cert: LabCertificationStatus | None,
    ) -> ModelRecord:
        """Set model lab certification status."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE models SET lab_cert = ? WHERE id = ?",
                (lab_cert.value if lab_cert else None, model_id),
            )
        if cursor.rowcount == 0:
            raise ModelNotFoundError(model_id)
        return self.get(model_id)

    def delete_by_repos(self, repos: Iterable[str]) -> int:
        """Delete all records whose repo is in the provided set."""
        repo_list = sorted(set(repos))
        if not repo_list:
            return 0
        placeholders = ", ".join("?" for _ in repo_list)
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM models WHERE repo IN ({placeholders})",
                repo_list,
            )
        return int(cursor.rowcount)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row mappings."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _record_values(record: ModelRecord) -> tuple[object, ...]:
        """Serialize a record for SQLite insertion."""
        return (
            record.id,
            record.repo,
            record.family,
            record.params_billion,
            record.active_params_billion,
            int(record.is_moe),
            record.quant,
            record.size_bytes,
            record.context_len,
            record.path,
            record.pool_role.value if record.pool_role else None,
            record.status.value,
            record.tok_per_sec,
            record.checksum_sha256,
            record.added_at.isoformat(),
            record.last_used.isoformat() if record.last_used else None,
            record.lab_cert.value if record.lab_cert else None,
            record.notes,
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ModelRecord:
        """Deserialize a SQLite row into a model record."""
        data = {column: row[column] for column in MODEL_COLUMNS}
        data["is_moe"] = bool(data["is_moe"])
        return ModelRecord.model_validate(data)


def register_many(registry: ModelRegistry, records: Iterable[ModelRecord]) -> list[ModelRecord]:
    """Register multiple records and return them."""
    return [registry.register(record) for record in records]
