from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from ois.infrastructure.postgres_fencing import PostgresWorkerLeaseStore, WorkerLease


@dataclass(frozen=True)
class SideEffectCommand:
    effect_id: str
    tenant_id: str
    execution_id: UUID
    invocation_id: str
    capability_id: str
    idempotency_key: str
    request: dict[str, Any]


@dataclass(frozen=True)
class SideEffectResult:
    effect_id: str
    idempotency_key: str
    output: Any = None
    completed_at: datetime | None = None


class SideEffectExecutor(Protocol):
    """External executor; implementations MUST pass idempotency_key downstream."""

    def execute(self, command: SideEffectCommand) -> SideEffectResult: ...


class TransactionalSideEffectBoundary:
    """Transactional outbox boundary for consequential external operations.

    The durable intent is committed before a worker performs the external effect.
    A worker may therefore crash after the external effect and before acknowledgement;
    recovery re-delivers the same idempotency key. Exactly-once effect semantics then
    depend on the downstream system honoring that key. The boundary itself guarantees
    durable intent, single logical command identity, and safe replay semantics.
    """

    def __init__(self, connection_factory: Any) -> None:
        self._connect = connection_factory

    def enqueue(
        self,
        *,
        tenant_id: str,
        execution_id: UUID,
        invocation_id: str,
        capability_id: str,
        idempotency_key: str,
        request: dict[str, Any],
        effect_id: str | None = None,
    ) -> SideEffectCommand:
        command = SideEffectCommand(
            effect_id=effect_id or str(uuid4()),
            tenant_id=tenant_id,
            execution_id=execution_id,
            invocation_id=invocation_id,
            capability_id=capability_id,
            idempotency_key=idempotency_key,
            request=request,
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
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
        return command

    def claim(self, *, worker_id: str) -> SideEffectCommand | None:
        """Atomically claim one pending/recoverable command using row locking."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT effect_id
                        FROM ois_side_effect_outbox
                        WHERE status = 'PENDING'
                           OR (status = 'PROCESSING' AND locked_at < now() - interval '5 minutes')
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE ois_side_effect_outbox AS outbox
                    SET status = 'PROCESSING',
                        attempts = attempts + 1,
                        locked_at = now(),
                        updated_at = now()
                                FROM candidate
                    WHERE outbox.effect_id = candidate.effect_id
                    RETURNING outbox.effect_id, outbox.tenant_id, outbox.execution_id,
                              outbox.invocation_id, outbox.capability_id,
                              outbox.idempotency_key, outbox.request
                    """
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            return None
        request = row[6]
        if isinstance(request, str):
            request = json.loads(request)
        return SideEffectCommand(
            effect_id=row[0],
            tenant_id=row[1],
            execution_id=row[2],
            invocation_id=row[3],
            capability_id=row[4],
            idempotency_key=row[5],
            request=dict(request),
        )

    def complete(
        self,
        command: SideEffectCommand,
        result: SideEffectResult,
        *,
        fencing: PostgresWorkerLeaseStore | None = None,
        worker_lease: WorkerLease | None = None,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if fencing is not None:
                    if worker_lease is None:
                        raise ValueError("fencing requires a worker lease")
                    fencing._assert_current_cursor(cursor, worker_lease)
                cursor.execute(
                    """
                    UPDATE ois_side_effect_outbox
                    SET status = 'COMPLETED',
                        completed_at = COALESCE(%s, now()),
                        result = %s::jsonb,
                        locked_at = NULL,
                        updated_at = now()
                    WHERE effect_id = %s
                    """,
                    (
                        result.completed_at,
                        json.dumps({"output": result.output}, sort_keys=True),
                        command.effect_id,
                    ),
                )
            connection.commit()

    def fail(
        self,
        command: SideEffectCommand,
        error: dict[str, Any],
        *,
        fencing: PostgresWorkerLeaseStore | None = None,
        worker_lease: WorkerLease | None = None,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if fencing is not None:
                    if worker_lease is None:
                        raise ValueError("fencing requires a worker lease")
                    fencing._assert_current_cursor(cursor, worker_lease)
                cursor.execute(
                    """
                    UPDATE ois_side_effect_outbox
                    SET status = 'PENDING',
                        locked_at = NULL,
                        last_error = %s::jsonb,
                        updated_at = now()
                    WHERE effect_id = %s
                    """,
                    (json.dumps(error, sort_keys=True), command.effect_id),
                )
            connection.commit()

    def recover_stale(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ois_side_effect_outbox
                    SET status = 'PENDING', locked_at = NULL, updated_at = now()
                    WHERE status = 'PROCESSING'
                      AND locked_at < now() - interval '5 minutes'
                    """
                )
                count = cursor.rowcount
            connection.commit()
        return int(count)
