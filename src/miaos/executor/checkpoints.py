"""SQLite checkpoint store for graph runs."""

import sqlite3
from pathlib import Path

from miaos.executor.events import GraphEvent


class CheckpointStore:
    """Persist graph run events in SQLite."""

    def __init__(self, db_path: Path) -> None:
        """Create and initialize a checkpoint store."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        """Create checkpoint tables if needed."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    node_id TEXT,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_graph_events_run ON graph_events(run_id, id)"
            )

    def append_event(self, event: GraphEvent) -> None:
        """Persist one graph event."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO graph_events
                    (run_id, trace_id, node_id, event_type, event_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.trace_id,
                    event.node_id,
                    event.event_type.value,
                    event.model_dump_json(),
                    event.ts.isoformat(),
                ),
            )

    def list_events(self, run_id: str) -> list[GraphEvent]:
        """Return persisted events for a run."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_json FROM graph_events WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [GraphEvent.model_validate_json(row[0]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection."""
        return sqlite3.connect(self.db_path)
