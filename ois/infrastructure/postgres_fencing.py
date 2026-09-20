"""PostgreSQL worker leases with epoch fencing for durable execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
    def _assert_current_cursor(cursor: Any, lease: WorkerLease) -> None:
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
            self._assert_current_cursor(cursor, lease)

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



class FencedPostgresDurableExecutionStore:
    """Mutation adapter that makes worker epoch ownership mandatory."""

    def __init__(
        self,
        durable_store: Any,
        lease_store: PostgresWorkerLeaseStore,
        lease: WorkerLease,
    ) -> None:
        self._store = durable_store
        self._lease_store = lease_store
        self.lease = lease

    def _assert(self, cursor: Any) -> None:
        self._lease_store._assert_current_cursor(cursor, self.lease)

    def load(self, execution_id: UUID) -> Any:
        return self._store.load(execution_id)

    def save(self, context: Any) -> None:
        context.touch()
        payload, digest = self._store._state_payload(context)
        with self._store.connection() as connection, connection.cursor() as cursor:
            self._assert(cursor)
            cursor.execute(
                self._store._checkpoint_sql(),
                (
                    context.identity.execution_id,
                    context.identity.tenant_id,
                    context.identity.workflow_id,
                    context.identity.workflow_version,
                    context.status.value,
                    payload,
                    digest,
                    context.created_at,
                    context.updated_at,
                ),
            )
            connection.commit()

    def put_idempotency(
        self,
        invocation_id: str,
        execution_id: UUID,
        tenant_id: str,
        result: Any,
    ) -> None:
        if result.status.value not in {"succeeded", "cancelled"}:
            return
        payload = {
            "invocation_id": result.invocation_id,
            "capability_id": result.capability_id,
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "metadata": dict(result.metadata),
        }
        with self._store.connection() as connection, connection.cursor() as cursor:
            self._assert(cursor)
            cursor.execute(
                """
                INSERT INTO ois_idempotency_results
                    (invocation_id, execution_id, tenant_id, capability_id, status, result)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (invocation_id) DO NOTHING
                """,
                (
                    invocation_id,
                    execution_id,
                    tenant_id,
                    result.capability_id,
                    result.status.value,
                    json.dumps(payload, sort_keys=True),
                ),
            )
            connection.commit()

    def get_idempotency(self, invocation_id: str) -> Any:
        return self._store.get_idempotency(invocation_id)

    def commit_checkpoint_and_side_effect(self, context: Any, command: Any) -> None:
        context.touch()
        payload, digest = self._store._state_payload(context)
        with self._store.connection() as connection, connection.cursor() as cursor:
            self._assert(cursor)
            cursor.execute(
                self._store._checkpoint_sql(),
                (
                    context.identity.execution_id,
                    context.identity.tenant_id,
                    context.identity.workflow_id,
                    context.identity.workflow_version,
                    context.status.value,
                    payload,
                    digest,
                    context.created_at,
                    context.updated_at,
                ),
            )
            cursor.execute(
                """
                INSERT INTO ois_side_effect_outbox (
                    effect_id, tenant_id, execution_id, invocation_id,
                    capability_id, idempotency_key, request
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (invocation_id) DO NOTHING
                """,
                (
                    command.effect_id,
                    command.tenant_id,
                    command.execution_id,
                    command.invocation_id,
                    command.capability_id,
                    command.idempotency_key,
                    json.dumps(command.request, sort_keys=True),
                ),
            )
            connection.commit()

    def complete_side_effect(self, command: Any, result: Any) -> None:
        with self._store.connection() as connection, connection.cursor() as cursor:
            self._assert(cursor)
            cursor.execute(
                """
                UPDATE ois_side_effect_outbox
                SET status = 'COMPLETED',
                    completed_at = COALESCE(%s, now()),
                    result = %s::jsonb,
                    locked_at = NULL,
                    updated_at = now()
                WHERE effect_id = %s AND execution_id = %s
                """,
                (
                    result.completed_at,
                    json.dumps({"output": result.output}, sort_keys=True),
                    command.effect_id,
                    command.execution_id,
                ),
            )
            if cursor.rowcount != 1:
                raise FencingError("side-effect completion target is missing")
            connection.commit()

    def delete(self, execution_id: UUID) -> None:
        with self._store.connection() as connection, connection.cursor() as cursor:
            self._assert(cursor)
            cursor.execute(
                "DELETE FROM ois_execution_checkpoints WHERE execution_id = %s",
                (execution_id,),
            )
            connection.commit()
