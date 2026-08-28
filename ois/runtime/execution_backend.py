"""Durable execution primitives behind the OIS runtime fabric contracts.

The backend provides a dependency-light SQLite execution store/queue and a
PostgreSQL worker queue that uses the Kernel's fenced execution leases. The
queue is a delivery primitive, not a second control plane: Kernel policy,
authorization, validation and recovery remain authoritative above it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from ois.kernel.postgres import LeaseLost, LeaseUnavailable, PostgreSQLExecutionCoordinator


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
    queue_name: str
    payload: dict[str, Any]
    attempts: int = 0
    lease_owner: str | None = None
    status: str = "queued"
    tenant_id: str = "default"
    lease_epoch: int | None = None


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

    def create(self, execution_id: str, workflow_id: str, payload: dict[str, Any]) -> ExecutionRecord:
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
    """Durable SQLite-backed worker queue with lease and retry semantics."""

    def __init__(self, database: str = ":memory:") -> None:
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS worker_queue (
                    job_id TEXT PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    updated_at TEXT NOT NULL
                )
                """
            )

    def enqueue(self, job_id: str, queue_name: str, payload: dict[str, Any]) -> QueueJob:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO worker_queue
                (job_id, queue_name, payload, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (job_id, queue_name, json.dumps(payload), _now()),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> QueueJob:
        row = self._connection.execute(
            "SELECT * FROM worker_queue WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"queue job not found: {job_id}")
        return QueueJob(
            job_id=row["job_id"],
            queue_name=row["queue_name"],
            payload=json.loads(row["payload"]),
            attempts=row["attempts"],
            lease_owner=row["lease_owner"],
            status=row["status"],
        )

    def claim(self, queue_name: str, worker_id: str) -> QueueJob | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                """
                SELECT job_id FROM worker_queue
                WHERE queue_name = ? AND status = 'queued' AND lease_owner IS NULL
                ORDER BY updated_at, job_id LIMIT 1
                """,
                (queue_name,),
            ).fetchone()
            if row is None:
                return None
            self._connection.execute(
                """
                UPDATE worker_queue
                SET lease_owner = ?, status = 'leased', updated_at = ?
                WHERE job_id = ? AND status = 'queued' AND lease_owner IS NULL
                """,
                (worker_id, _now(), row["job_id"]),
            )
        return self.get(row["job_id"])

    def retry(self, job_id: str, worker_id: str) -> QueueJob:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE worker_queue
                SET attempts = attempts + 1,
                    lease_owner = NULL,
                    status = 'queued',
                    updated_at = ?
                WHERE job_id = ? AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"worker does not own queue job: {job_id}")
        return self.get(job_id)

    def acknowledge(self, job_id: str, worker_id: str) -> QueueJob:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                UPDATE worker_queue
                SET status = 'completed', updated_at = ?
                WHERE job_id = ? AND lease_owner = ?
                """,
                (_now(), job_id, worker_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"worker does not own queue job: {job_id}")
        return self.get(job_id)


class PostgreSQLWorkerQueue:
    """PostgreSQL-backed queue fenced by Kernel execution lease epochs."""

    def __init__(
        self,
        dsn: str,
        *,
        coordinator: PostgreSQLExecutionCoordinator | None = None,
        initialize: bool = True,
        lease_ttl_seconds: float = 30.0,
    ) -> None:
        self._dsn = dsn
        self._coordinator = coordinator or PostgreSQLExecutionCoordinator(dsn, initialize=False)
        self._lease_ttl_seconds = lease_ttl_seconds
        if initialize:
            self.initialize()

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
        return psycopg.connect(self._dsn)

    @staticmethod
    def _fence_id(job_id: str, queue_name: str, tenant_id: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"ois:worker-queue:{tenant_id}:{queue_name}:{job_id}")

    def initialize(self) -> None:
        self._coordinator.initialize()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ois_worker_queue (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    fence_id UUID NOT NULL UNIQUE,
                    lease_owner TEXT,
                    lease_epoch BIGINT,
                    status TEXT NOT NULL DEFAULT 'queued',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS ois_worker_queue_ready_idx
                    ON ois_worker_queue (queue_name, status, updated_at, job_id);
                """
            )

    def enqueue(
        self,
        job_id: str,
        queue_name: str,
        payload: dict[str, Any],
        *,
        tenant_id: str = "default",
    ) -> QueueJob:
        fence_id = self._fence_id(job_id, queue_name, tenant_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_worker_queue
                    (job_id, tenant_id, queue_name, payload, fence_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (job_id, tenant_id, queue_name, _jsonb(payload), fence_id),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> QueueJob:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT job_id, tenant_id, queue_name, payload, attempts,
                       lease_owner, lease_epoch, status
                FROM ois_worker_queue WHERE job_id = %s
                """,
                (job_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise LookupError(f"queue job not found: {job_id}")
        return QueueJob(
            job_id=str(row[0]),
            tenant_id=str(row[1]),
            queue_name=str(row[2]),
            payload=dict(row[3]),
            attempts=int(row[4]),
            lease_owner=row[5],
            lease_epoch=int(row[6]) if row[6] is not None else None,
            status=str(row[7]),
        )

    def claim(self, queue_name: str, worker_id: str, *, tenant_id: str = "default") -> QueueJob | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT q.job_id, q.fence_id, q.status, q.lease_epoch
                FROM ois_worker_queue AS q
                LEFT JOIN ois_execution_leases AS l ON l.execution_id = q.fence_id
                WHERE q.tenant_id = %s AND q.queue_name = %s
                  AND (
                    q.status = 'queued'
                    OR (q.status = 'leased' AND (l.expires_at IS NULL OR l.expires_at <= CURRENT_TIMESTAMP))
                  )
                ORDER BY q.updated_at, q.job_id
                LIMIT 1
                """,
                (tenant_id, queue_name),
            )
            row = cursor.fetchone()
        if row is None:
            return None

        job_id = str(row[0])
        fence_id = row[1]
        previous_epoch = int(row[3]) if row[3] is not None else 0
        try:
            lease = self._coordinator.claim(
                fence_id,
                tenant_id,
                worker_id,
                ttl_seconds=self._lease_ttl_seconds,
            )
        except LeaseUnavailable:
            return None

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET lease_owner = %s,
                    lease_epoch = %s,
                    attempts = CASE WHEN status = 'leased' THEN attempts + 1 ELSE attempts END,
                    status = 'leased',
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s
                  AND status IN ('queued', 'leased')
                  AND COALESCE(lease_epoch, 0) < %s
                RETURNING job_id
                """,
                (worker_id, lease.lease_epoch, job_id, lease.lease_epoch),
            )
            claimed = cursor.fetchone()

        if claimed is None or lease.lease_epoch <= previous_epoch:
            self._coordinator.release(lease)
            return None
        return self.get(job_id)

    def heartbeat(self, job_id: str, worker_id: str) -> QueueJob:
        job = self.get(job_id)
        if job.lease_epoch is None:
            raise LeaseLost(f"queue job is not leased: {job_id}")
        lease = self._coordinator.renew(
            self._lease(job),
            ttl_seconds=self._lease_ttl_seconds,
        )
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET lease_epoch = %s, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s AND lease_owner = %s AND lease_epoch = %s
                """,
                (lease.lease_epoch, job_id, worker_id, job.lease_epoch),
            )
        return self.get(job_id)

    def retry(self, job_id: str, worker_id: str) -> QueueJob:
        job = self.get(job_id)
        lease = self._lease(job)
        self._coordinator.assert_current(lease)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue AS q
                SET attempts = q.attempts + 1,
                    lease_owner = NULL,
                    lease_epoch = NULL,
                    status = 'queued',
                    updated_at = CURRENT_TIMESTAMP
                WHERE q.job_id = %s
                  AND q.lease_owner = %s
                  AND q.lease_epoch = %s
                  AND EXISTS (
                    SELECT 1 FROM ois_execution_leases AS l
                    WHERE l.execution_id = q.fence_id
                      AND l.worker_id = %s
                      AND l.lease_epoch = q.lease_epoch
                      AND l.state = 'active'
                      AND l.expires_at > CURRENT_TIMESTAMP
                  )
                """,
                (job_id, worker_id, lease.lease_epoch, worker_id),
            )
            if cursor.rowcount == 0:
                raise LeaseLost(f"lease lost for queue job {job_id}")
        self._coordinator.release(lease)
        return self.get(job_id)

    def acknowledge(self, job_id: str, worker_id: str) -> QueueJob:
        job = self.get(job_id)
        lease = self._lease(job)
        self._coordinator.assert_current(lease)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue AS q
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE q.job_id = %s
                  AND q.lease_owner = %s
                  AND q.lease_epoch = %s
                  AND EXISTS (
                    SELECT 1 FROM ois_execution_leases AS l
                    WHERE l.execution_id = q.fence_id
                      AND l.worker_id = %s
                      AND l.lease_epoch = q.lease_epoch
                      AND l.state = 'active'
                      AND l.expires_at > CURRENT_TIMESTAMP
                  )
                """,
                (job_id, worker_id, lease.lease_epoch, worker_id),
            )
            if cursor.rowcount == 0:
                raise LeaseLost(f"lease lost for queue job {job_id}")
        self._coordinator.release(lease)
        return self.get(job_id)

    @staticmethod
    def _lease(job: QueueJob):
        if job.lease_owner is None or job.lease_epoch is None:
            raise LeaseLost(f"queue job is not leased: {job.job_id}")
        return _QueueLease(job)


def _jsonb(value: dict[str, Any]) -> Any:
    try:
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
    return Jsonb(value)


class _QueueLease:
    """Minimal adapter matching PostgreSQLExecutionCoordinator lease attributes."""

    def __init__(self, job: QueueJob) -> None:
        from datetime import datetime, timezone

        self.execution_id = PostgreSQLWorkerQueue._fence_id(job.job_id, job.queue_name, job.tenant_id)
        self.tenant_id = job.tenant_id
        self.worker_id = job.lease_owner
        self.lease_epoch = job.lease_epoch
        self.expires_at = datetime.now(timezone.utc)
