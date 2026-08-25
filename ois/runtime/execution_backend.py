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


@dataclass(frozen=True)
class QueueJob:
    job_id: str
    queue: str
    payload: dict[str, Any]
    attempts: int = 0
    lease_owner: str | None = None
    status: str = "ready"


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


class SQLiteWorkerQueue:
    """Durable queue with explicit claim, retry and acknowledgement semantics."""

    def __init__(self, database: str = ":memory:") -> None:
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_jobs (
                    job_id TEXT PRIMARY KEY,
                    queue TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    status TEXT NOT NULL DEFAULT 'ready',
                    updated_at TEXT NOT NULL
                )
                """
            )

    def enqueue(self, job_id: str, queue: str, payload: dict[str, Any]) -> QueueJob:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO worker_jobs
                (job_id, queue, payload, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, queue, json.dumps(payload), _now()),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> QueueJob:
        row = self._connection.execute(
            "SELECT * FROM worker_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"job not found: {job_id}")
        return QueueJob(
            job_id=row["job_id"],
            queue=row["queue"],
            payload=json.loads(row["payload"]),
            attempts=row["attempts"],
            lease_owner=row["lease_owner"],
            status=row["status"],
        )

    def claim(self, queue: str, worker_id: str) -> QueueJob | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT job_id FROM worker_jobs
                WHERE queue = ? AND status = 'ready'
                ORDER BY updated_at, job_id LIMIT 1
                """,
                (queue,),
            ).fetchone()
            if row is None:
                return None
            self._connection.execute(
                """
                UPDATE worker_jobs
                SET lease_owner = ?, status = 'leased', updated_at = ?
                WHERE job_id = ? AND status = 'ready'
                """,
                (worker_id, _now(), row["job_id"]),
            )
        return self.get(row["job_id"])

    def retry(self, job_id: str, worker_id: str) -> QueueJob:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE worker_jobs
                SET attempts = attempts + 1, lease_owner = NULL,
                    status = 'ready', updated_at = ?
                WHERE job_id = ? AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )
        return self.get(job_id)

    def acknowledge(self, job_id: str, worker_id: str) -> QueueJob:
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE worker_jobs
                SET status = 'succeeded', updated_at = ?
                WHERE job_id = ? AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )
        return self.get(job_id)
