"""PostgreSQL durable implementations of the Kernel persistence contracts.

The backend keeps checkpoint and completed-invocation state in PostgreSQL JSONB
columns so the Python execution contracts remain the source of truth while the
storage layer provides process-independent durability and database concurrency.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from .checkpoint import CheckpointNotFound
from .contracts import InvocationResult
from .state import ExecutionContext
from .types import ExecutionStatus, FailureClass, InvocationStatus, RiskLevel

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ois_checkpoints (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id TEXT,
    workflow_version TEXT,
    context JSONB NOT NULL,
    revision BIGINT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ois_idempotency_results (
    invocation_id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ois_checkpoints_tenant_idx
    ON ois_checkpoints (tenant_id);

CREATE INDEX IF NOT EXISTS ois_checkpoints_updated_idx
    ON ois_checkpoints (updated_at DESC);
"""


class PostgreSQLCheckpointStore:
    """PostgreSQL implementation of :class:`CheckpointStore`.

    Each operation uses its own short-lived connection and transaction, making
    the store safe for callers using threads or separate runtime processes.
    Checkpoint writes are atomic upserts; PostgreSQL serializes conflicting
    writes on the execution primary key and increments a durable revision.
    """

    def __init__(self, dsn: str, *, initialize: bool = True) -> None:
        self._dsn = dsn
        if initialize:
            self.initialize()

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - exercised by packaging tests
            raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
        return psycopg.connect(self._dsn)

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(_SCHEMA)

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        payload = context.to_dict()
        identity = context.identity
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    INSERT INTO ois_checkpoints (
                        execution_id, tenant_id, workflow_id, workflow_version,
                        context, revision, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                    ON CONFLICT (execution_id) DO UPDATE SET
                        tenant_id = EXCLUDED.tenant_id,
                        workflow_id = EXCLUDED.workflow_id,
                        workflow_version = EXCLUDED.workflow_version,
                        context = EXCLUDED.context,
                        revision = ois_checkpoints.revision + 1,
                        updated_at = EXCLUDED.updated_at
                    """,
                (
                    identity.execution_id,
                    identity.tenant_id,
                    identity.workflow_id,
                    identity.workflow_version,
                    _jsonb(payload),
                    context.created_at,
                    context.updated_at,
                ),
            )

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT context FROM ois_checkpoints WHERE execution_id = %s",
                (execution_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
        return _context_from_payload(row[0])

    def delete(self, execution_id: UUID) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM ois_checkpoints WHERE execution_id = %s",
                (execution_id,),
            )

    def exists(self, execution_id: UUID) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ois_checkpoints WHERE execution_id = %s",
                (execution_id,),
            )
            return cursor.fetchone() is not None

    def revision(self, execution_id: UUID) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT revision FROM ois_checkpoints WHERE execution_id = %s",
                (execution_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
        return int(row[0])

    def close(self) -> None:
        """Compatibility no-op; operations use short-lived connections."""


class PostgreSQLIdempotencyStore:
    """PostgreSQL implementation of :class:`IdempotencyStore`.

    ``put`` follows the existing contract's replacement semantics. The
    additional ``put_if_absent`` primitive provides an atomic first-writer-wins
    operation for callers that must coordinate concurrent duplicate work.
    """

    def __init__(self, dsn: str, *, initialize: bool = True) -> None:
        self._dsn = dsn
        if initialize:
            self.initialize()

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
        return psycopg.connect(self._dsn)

    def initialize(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(_SCHEMA)

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    SELECT result
                    FROM ois_idempotency_results
                    WHERE invocation_id = %s
                    """,
                (invocation_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return _result_from_payload(row[0])

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        payload = _result_to_payload(result)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    INSERT INTO ois_idempotency_results (
                        invocation_id, capability_id, status, result
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (invocation_id) DO UPDATE SET
                        capability_id = EXCLUDED.capability_id,
                        status = EXCLUDED.status,
                        result = EXCLUDED.result,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                (
                    invocation_id,
                    result.capability_id,
                    result.status.value,
                    _jsonb(payload),
                ),
            )

    def put_if_absent(self, invocation_id: str, result: InvocationResult) -> bool:
        """Atomically persist the first result for an invocation id.

        Returns ``True`` only for the transaction that inserted the row. A
        concurrent duplicate receives ``False`` without overwriting the winner.
        """
        payload = _result_to_payload(result)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    INSERT INTO ois_idempotency_results (
                        invocation_id, capability_id, status, result
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (invocation_id) DO NOTHING
                    RETURNING invocation_id
                    """,
                (
                    invocation_id,
                    result.capability_id,
                    result.status.value,
                    _jsonb(payload),
                ),
            )
            return cursor.fetchone() is not None

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None

    def close(self) -> None:
        """Compatibility no-op; operations use short-lived connections."""


def _jsonb(value: Mapping[str, object]) -> Any:
    try:
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PostgreSQL support requires the 'psycopg' package.") from exc
    return Jsonb(dict(value))


def _context_from_payload(raw: object) -> ExecutionContext:
    payload = dict(raw) if isinstance(raw, Mapping) else json.loads(str(raw))
    if payload.get("status") is not None:
        payload["status"] = ExecutionStatus(payload["status"])
    if payload.get("risk_level") is not None:
        payload["risk_level"] = RiskLevel(payload["risk_level"])
    if payload.get("last_failure") is not None:
        payload["last_failure"] = FailureClass(payload["last_failure"])
    for field in ("created_at", "updated_at"):
        if isinstance(payload.get(field), str):
            payload[field] = datetime.fromisoformat(payload[field])
    return ExecutionContext.from_dict(payload)


def _result_to_payload(result: InvocationResult) -> dict[str, object]:
    return {
        "invocation_id": result.invocation_id,
        "capability_id": result.capability_id,
        "status": result.status.value,
        "output": result.output,
        "error": dict(result.error) if result.error is not None else None,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "metadata": dict(result.metadata),
    }


def _result_from_payload(raw: object) -> InvocationResult:
    payload = dict(raw) if isinstance(raw, Mapping) else json.loads(str(raw))
    return InvocationResult(
        invocation_id=str(payload["invocation_id"]),
        capability_id=str(payload["capability_id"]),
        status=InvocationStatus(payload["status"]),
        output=payload.get("output"),
        error=payload.get("error"),
        started_at=payload.get("started_at"),
        completed_at=payload.get("completed_at"),
        metadata=payload.get("metadata", {}),
    )
