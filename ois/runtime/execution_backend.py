"""Durable execution primitives behind the OIS runtime fabric contracts.

The backend uses SQLite from the standard library so the first durable
implementation remains dependency-light. It is an execution store and queue,
not a second control plane: Kernel policy, authorization, validation and
recovery remain authoritative above it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    workflow_id: str
    status: str
    payload: dict[str, Any]
    result: Any = None
    error: dict[str, str] | None = None
    checkpoint: dict[str, Any] | None = None


class SQLiteExecutionStore:
    """Persistent execution/checkpoint store for resumable workflows."""

    def __init__(self, database: str = ":memory:") -> None:
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    checkpoint TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create(
        self,
        execution_id: str,
        workflow_id: str,
        payload: dict[str, Any],
    ) -> ExecutionRecord:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO executions
                (execution_id, workflow_id, status, payload, updated_at)
                VALUES (?, ?, 'ready', ?, ?)
                """,
                (execution_id, workflow_id, json.dumps(payload), _now()),
            )
        return self.get(execution_id)

    def checkpoint(self, execution_id: str, checkpoint: dict[str, Any]) -> ExecutionRecord:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE executions
                SET checkpoint = ?, status = 'running', updated_at = ?
                WHERE execution_id = ?
                """,
                (json.dumps(checkpoint), _now(), execution_id),
            )
        return self.get(execution_id)

    def complete(self, execution_id: str, result: Any) -> ExecutionRecord:
        return self._set_terminal(execution_id, "succeeded", result=result)

    def fail(self, execution_id: str, error: dict[str, str]) -> ExecutionRecord:
        return self._set_terminal(execution_id, "failed", error=error)

    def _set_terminal(
        self,
        execution_id: str,
        status: str,
        *,
        result: Any = None,
        error: dict[str, str] | None = None,
    ) -> ExecutionRecord:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE executions
                SET status = ?, result = ?, error = ?, updated_at = ?
                WHERE execution_id = ?
                """,
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    json.dumps(error) if error is not None else None,
                    _now(),
                    execution_id,
                ),
            )
        return self.get(execution_id)

    def get(self, execution_id: str) -> ExecutionRecord:
        row = self._connection.execute(
            "SELECT * FROM executions WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"execution not found: {execution_id}")
        return ExecutionRecord(
            execution_id=row["execution_id"],
            workflow_id=row["workflow_id"],
            status=row["status"],
            payload=json.loads(row["payload"]),
            result=json.loads(row["result"]) if row["result"] else None,
            error=json.loads(row["error"]) if row["error"] else None,
            checkpoint=json.loads(row["checkpoint"]) if row["checkpoint"] else None,
        )
