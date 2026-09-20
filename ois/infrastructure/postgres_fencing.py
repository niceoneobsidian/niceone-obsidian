"""PostgreSQL worker leases with epoch fencing for durable execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID


class FencingError(RuntimeError):
    """Raised when a worker no longer owns the current execution epoch."""


@dataclass(frozen=True)
class WorkerLease:
    execution_id: UUID
    worker_id: str
    epoch: int
    lease_expires_at: datetime


class PostgresWorkerLeaseStore:
    """Authoritative PostgreSQL worker ownership and fencing boundary."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS ois_worker_leases (
        execution_id UUID PRIMARY KEY,
        worker_id TEXT NOT NULL,
        epoch BIGINT NOT NULL,
        lease_expires_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_ois_worker_leases_expiry
        ON ois_worker_leases (lease_expires_at);
    """

    def __init__(self, connection_factory: Any, *, ttl_seconds: float = 30.0) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._connect = connection_factory
        self._ttl_seconds = ttl_seconds

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(self.SCHEMA)
        # psycopg context managers commit successful transactions.

    def claim(self, execution_id: UUID, worker_id: str) -> WorkerLease | None:
        if not worker_id:
            raise ValueError("worker_id must not be empty")
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT worker_id, epoch, lease_expires_at
                FROM ois_worker_leases
                WHERE execution_id = %s
                FOR UPDATE
                """,
                (execution_id,),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO ois_worker_leases
                        (execution_id, worker_id, epoch, lease_expires_at)
                    VALUES (%s, %s, 1, now() + (%s * interval '1 second'))
                    RETURNING epoch, lease_expires_at
                    """,
                    (execution_id, worker_id, self._ttl_seconds),
                )
                epoch, expires = cursor.fetchone()
                return WorkerLease(execution_id, worker_id, int(epoch), expires)

            current_worker, current_epoch, expires = row
            if expires > datetime.now(expires.tzinfo) and current_worker != worker_id:
                return None

            if current_worker == worker_id and expires > datetime.now(expires.tzinfo):
                next_epoch = int(current_epoch)
            else:
                next_epoch = int(current_epoch) + 1

            cursor.execute(
                """
                UPDATE ois_worker_leases
                SET worker_id = %s,
                    epoch = %s,
                    lease_expires_at = now() + (%s * interval '1 second'),
                    updated_at = now()
                WHERE execution_id = %s
                RETURNING epoch, lease_expires_at
                """,
                (worker_id, next_epoch, self._ttl_seconds, execution_id),
            )
            epoch, new_expires = cursor.fetchone()
            return WorkerLease(execution_id, worker_id, int(epoch), new_expires)

    @staticmethod
    def assert_current(cursor: Any, lease: WorkerLease) -> None:
        cursor.execute(
            """
            SELECT 1
            FROM ois_worker_leases
            WHERE execution_id = %s
              AND worker_id = %s
              AND epoch = %s
              AND lease_expires_at > now()
            FOR UPDATE
            """,
            (lease.execution_id, lease.worker_id, lease.epoch),
        )
        if cursor.fetchone() is None:
            raise FencingError(
                f"stale or expired worker lease: execution={lease.execution_id} "
                f"worker={lease.worker_id} epoch={lease.epoch}"
            )

    def assert_current(self, lease: WorkerLease) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            self.assert_current(cursor, lease)

    def renew(self, lease: WorkerLease) -> WorkerLease:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_worker_leases
                SET lease_expires_at = now() + (%s * interval '1 second'),
                    updated_at = now()
                WHERE execution_id = %s
                  AND worker_id = %s
                  AND epoch = %s
                  AND lease_expires_at > now()
                RETURNING epoch, lease_expires_at
                """,
                (self._ttl_seconds, lease.execution_id, lease.worker_id, lease.epoch),
            )
            row = cursor.fetchone()
            if row is None:
                raise FencingError("cannot renew a stale or expired worker lease")
            epoch, expires = row
            return WorkerLease(lease.execution_id, lease.worker_id, int(epoch), expires)

    def release(self, lease: WorkerLease) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM ois_worker_leases
                WHERE execution_id = %s AND worker_id = %s AND epoch = %s
                """,
                (lease.execution_id, lease.worker_id, lease.epoch),
            )
