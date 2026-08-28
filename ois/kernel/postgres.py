"""PostgreSQL durability and fenced worker coordination for OIS."""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
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
CREATE INDEX IF NOT EXISTS ois_checkpoints_tenant_idx ON ois_checkpoints (tenant_id);
CREATE INDEX IF NOT EXISTS ois_checkpoints_updated_idx ON ois_checkpoints (updated_at DESC);
CREATE TABLE IF NOT EXISTS ois_execution_leases (
    execution_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    lease_epoch BIGINT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL DEFAULT 'active'
);
CREATE INDEX IF NOT EXISTS ois_execution_leases_expiry_idx ON ois_execution_leases (expires_at);
CREATE INDEX IF NOT EXISTS ois_execution_leases_worker_idx ON ois_execution_leases (worker_id);
"""


class PostgreSQLCheckpointStore:
    """Process-independent implementation of the kernel checkpoint contract."""

    def __init__(self, dsn: str, *, initialize: bool = True) -> None:
        self._dsn = dsn
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

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        identity = context.identity
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_checkpoints
                    (execution_id, tenant_id, workflow_id, workflow_version, context,
                     revision, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (execution_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    workflow_id = EXCLUDED.workflow_id,
                    workflow_version = EXCLUDED.workflow_version,
                    context = EXCLUDED.context,
                    revision = ois_checkpoints.revision + 1,
                    updated_at = EXCLUDED.updated_at
                """,
                (identity.execution_id, identity.tenant_id, identity.workflow_id,
                 identity.workflow_version, _jsonb(context.to_dict()), context.created_at,
                 context.updated_at),
            )

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT context FROM ois_checkpoints WHERE execution_id = %s", (execution_id,))
            row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
        return _context_from_payload(row[0])

    def delete(self, execution_id: UUID) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM ois_checkpoints WHERE execution_id = %s", (execution_id,))

    def exists(self, execution_id: UUID) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM ois_checkpoints WHERE execution_id = %s", (execution_id,))
            return cursor.fetchone() is not None

    def revision(self, execution_id: UUID) -> int:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT revision FROM ois_checkpoints WHERE execution_id = %s", (execution_id,))
            row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
        return int(row[0])

    def close(self) -> None:
        pass


class PostgreSQLIdempotencyStore:
    """Durable completed-invocation store with atomic first-writer-wins."""

    def __init__(self, dsn: str, *, initialize: bool = True) -> None:
        self._dsn = dsn
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

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT result FROM ois_idempotency_results WHERE invocation_id = %s", (invocation_id,))
            row = cursor.fetchone()
        return None if row is None else _result_from_payload(row[0])

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_idempotency_results
                    (invocation_id, capability_id, status, result)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (invocation_id) DO NOTHING
                """,
                (invocation_id, result.capability_id, result.status.value, _jsonb(_result_to_payload(result))),
            )

    def put_if_absent(self, invocation_id: str, result: InvocationResult) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ois_idempotency_results
                    (invocation_id, capability_id, status, result)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (invocation_id) DO NOTHING
                RETURNING invocation_id
                """,
                (invocation_id, result.capability_id, result.status.value, _jsonb(_result_to_payload(result))),
            )
            return cursor.fetchone() is not None

    def exists(self, invocation_id: str) -> bool:
        return self.get(invocation_id) is not None

    def close(self) -> None:
        pass


class LeaseLost(RuntimeError):
    """Raised when a worker attempts a fenced operation with a stale lease."""


class LeaseUnavailable(RuntimeError):
    """Raised when an execution is currently owned by another live worker."""


class ExecutionLease:
    def __init__(self, execution_id: UUID, tenant_id: str, worker_id: str, lease_epoch: int,
                 expires_at: datetime) -> None:
        self.execution_id = execution_id
        self.tenant_id = tenant_id
        self.worker_id = worker_id
        self.lease_epoch = lease_epoch
        self.expires_at = expires_at


class PostgreSQLExecutionCoordinator:
    """PostgreSQL lease coordinator with monotonically increasing fencing epochs."""

    def __init__(self, dsn: str, *, initialize: bool = True) -> None:
        self._dsn = dsn
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

    def claim(self, execution_id: UUID, tenant_id: str, worker_id: str,
              ttl_seconds: float = 30.0) -> ExecutionLease:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=ttl_seconds)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT worker_id, lease_epoch, expires_at FROM ois_execution_leases "
                "WHERE execution_id = %s FOR UPDATE",
                (execution_id,),
            )
            row = cursor.fetchone()
            if row is not None and row[2] > now and row[0] != worker_id:
                raise LeaseUnavailable(f"execution {execution_id} is owned by {row[0]}")
            epoch = (int(row[1]) + 1) if row is not None else 1
            cursor.execute(
                """
                INSERT INTO ois_execution_leases
                    (execution_id, tenant_id, worker_id, lease_epoch, claimed_at,
                     heartbeat_at, expires_at, state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                ON CONFLICT (execution_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    worker_id = EXCLUDED.worker_id,
                    lease_epoch = EXCLUDED.lease_epoch,
                    claimed_at = EXCLUDED.claimed_at,
                    heartbeat_at = EXCLUDED.heartbeat_at,
                    expires_at = EXCLUDED.expires_at,
                    state = 'active'
                """,
                (execution_id, tenant_id, worker_id, epoch, now, now, expires),
            )
        return ExecutionLease(execution_id, tenant_id, worker_id, epoch, expires)

    def renew(self, lease: ExecutionLease, ttl_seconds: float = 30.0) -> ExecutionLease:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=ttl_seconds)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_execution_leases
                SET heartbeat_at = %s, expires_at = %s
                WHERE execution_id = %s AND worker_id = %s AND lease_epoch = %s
                  AND expires_at > %s AND state = 'active'
                RETURNING expires_at
                """,
                (now, expires, lease.execution_id, lease.worker_id, lease.lease_epoch, now),
            )
            row = cursor.fetchone()
        if row is None:
            raise LeaseLost(f"lease lost for execution {lease.execution_id}")
        return ExecutionLease(lease.execution_id, lease.tenant_id, lease.worker_id,
                              lease.lease_epoch, row[0])

    def assert_current(self, lease: ExecutionLease) -> None:
        now = datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM ois_execution_leases
                WHERE execution_id = %s AND worker_id = %s AND lease_epoch = %s
                  AND expires_at > %s AND state = 'active'
                """,
                (lease.execution_id, lease.worker_id, lease.lease_epoch, now),
            )
            if cursor.fetchone() is None:
                raise LeaseLost(f"lease lost for execution {lease.execution_id}")

    def release(self, lease: ExecutionLease) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE ois_execution_leases SET state = 'released'
                WHERE execution_id = %s AND worker_id = %s AND lease_epoch = %s
                """,
                (lease.execution_id, lease.worker_id, lease.lease_epoch),
            )


def _jsonb(value: Mapping[str, object]) -> Any:
    from psycopg.types.json import Jsonb
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
