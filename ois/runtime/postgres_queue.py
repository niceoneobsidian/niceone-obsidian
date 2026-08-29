"""PostgreSQL-backed durable worker queue using execution fencing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from ois.kernel.postgres import ExecutionLease, LeaseLost, PostgreSQLExecutionCoordinator


@dataclass(frozen=True)
class PostgreSQLQueueJob:
    job_id: str
    queue: str
    payload: dict[str, Any]
    execution_id: UUID
    tenant_id: str
    status: str
    attempts: int
    lease_owner: str | None
    lease_epoch: int | None
    lease_expires_at: datetime | None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ois_worker_queue (
    job_id TEXT PRIMARY KEY,
    queue TEXT NOT NULL,
    payload JSONB NOT NULL,
    execution_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_owner TEXT,
    lease_epoch BIGINT,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ois_worker_queue_ready_idx
    ON ois_worker_queue (queue, status, updated_at);
CREATE INDEX IF NOT EXISTS ois_worker_queue_expiry_idx
    ON ois_worker_queue (queue, lease_expires_at);
"""


class PostgreSQLWorkerQueue:
    """Durable queue whose worker ownership is fenced by execution epochs."""

    def __init__(
        self,
        dsn: str,
        *,
        coordinator: PostgreSQLExecutionCoordinator | None = None,
        initialize: bool = True,
    ) -> None:
        self._dsn = dsn
        self.coordinator = coordinator or PostgreSQLExecutionCoordinator(
            dsn, initialize=initialize
        )
        if initialize:
            self.initialize()

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
        return psycopg.connect(self._dsn)

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(_SCHEMA)

    def enqueue(
        self,
        job_id: str,
        queue: str,
        payload: dict[str, Any],
        *,
        execution_id: UUID | None = None,
        tenant_id: str = "default",
    ) -> PostgreSQLQueueJob:
        execution_id = execution_id or uuid4()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_worker_queue
                    (job_id, queue, payload, execution_id, tenant_id, status,
                     attempts, lease_owner, lease_epoch, lease_expires_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'queued', 0, NULL, NULL, NULL, CURRENT_TIMESTAMP)
                """,
                (job_id, queue, _jsonb(payload), execution_id, tenant_id),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> PostgreSQLQueueJob:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM ois_worker_queue WHERE job_id = %s", (job_id,))
            row = cursor.fetchone()
        if row is None:
            raise LookupError(f"queue job not found: {job_id}")
        return self._job(row)

    def claim(
        self,
        queue: str,
        worker_id: str,
        *,
        ttl_seconds: float = 30.0,
    ) -> PostgreSQLQueueJob | None:
        now = datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT job_id, execution_id, tenant_id
                FROM ois_worker_queue
                WHERE queue = %s
                  AND (
                    status = 'queued'
                    OR (status = 'leased' AND lease_expires_at <= %s)
                  )
                ORDER BY updated_at, job_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (queue, now),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            lease = self.coordinator.claim(
                row[1],
                row[2],
                worker_id,
                ttl_seconds=ttl_seconds,
            )
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET status = 'leased', lease_owner = %s, lease_epoch = %s,
                    lease_expires_at = %s, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s
                """,
                (worker_id, lease.lease_epoch, lease.expires_at, row[0]),
            )
        return self.get(row[0])

    def renew(
        self,
        job_id: str,
        worker_id: str,
        lease_epoch: int,
        *,
        ttl_seconds: float = 30.0,
    ) -> PostgreSQLQueueJob:
        job = self.get(job_id)
        lease = self._lease_for(job, worker_id, lease_epoch)
        renewed = self.coordinator.renew(lease, ttl_seconds=ttl_seconds)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET lease_expires_at = %s, updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s AND lease_owner = %s AND lease_epoch = %s AND status = 'leased'
                """,
                (renewed.expires_at, job_id, worker_id, lease_epoch),
            )
        return self.get(job_id)

    def retry(self, job_id: str, worker_id: str, lease_epoch: int) -> PostgreSQLQueueJob:
        job = self.get(job_id)
        lease = self._lease_for(job, worker_id, lease_epoch)
        self.coordinator.assert_current(lease)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET status = 'queued', attempts = attempts + 1,
                    lease_owner = NULL, lease_epoch = NULL, lease_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s AND status = 'leased'
                  AND lease_owner = %s AND lease_epoch = %s
                """,
                (job_id, worker_id, lease_epoch),
            )
            if cursor.rowcount != 1:
                raise LeaseLost(f"queue lease lost for job {job_id}")
        self.coordinator.release(lease)
        return self.get(job_id)

    def acknowledge(
        self,
        job_id: str,
        worker_id: str,
        lease_epoch: int,
    ) -> PostgreSQLQueueJob:
        job = self.get(job_id)
        lease = self._lease_for(job, worker_id, lease_epoch)
        self.coordinator.assert_current(lease)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_queue
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE job_id = %s AND status = 'leased'
                  AND lease_owner = %s AND lease_epoch = %s
                """,
                (job_id, worker_id, lease_epoch),
            )
            if cursor.rowcount != 1:
                raise LeaseLost(f"queue lease lost for job {job_id}")
        self.coordinator.release(lease)
        return self.get(job_id)

    def _lease_for(
        self,
        job: PostgreSQLQueueJob,
        worker_id: str,
        lease_epoch: int,
    ) -> ExecutionLease:
        if (
            job.lease_owner != worker_id
            or job.lease_epoch != lease_epoch
            or job.lease_expires_at is None
        ):
            raise LeaseLost(f"queue lease lost for job {job.job_id}")
        return ExecutionLease(
            job.execution_id,
            job.tenant_id,
            worker_id,
            lease_epoch,
            job.lease_expires_at,
        )

    @staticmethod
    def _job(row: tuple[Any, ...]) -> PostgreSQLQueueJob:
        return PostgreSQLQueueJob(
            job_id=row[0],
            queue=row[1],
            payload=dict(row[2]),
            execution_id=row[3],
            tenant_id=row[4],
            status=row[5],
            attempts=int(row[6]),
            lease_owner=row[7],
            lease_epoch=int(row[8]) if row[8] is not None else None,
            lease_expires_at=row[9],
        )


def _jsonb(value: dict[str, Any]) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)
