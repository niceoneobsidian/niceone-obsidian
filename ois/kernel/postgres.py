from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from .checkpoint import CheckpointNotFound
from .contracts import InvocationResult
from .side_effects import SideEffectCommand
from .state import ExecutionContext
from .types import InvocationStatus

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    psycopg = None  # type: ignore[assignment]


class PostgresConfigurationError(RuntimeError):
    """Raised when the PostgreSQL driver/configuration is unavailable."""


class PostgresDurableExecutionStore:
    """PostgreSQL system-of-record for durable OIS execution state.

    The current-state table supports fast resume while the append-only history table
    preserves every checkpoint mutation for recovery, audit, and evidence.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS ois_execution_checkpoints (
        execution_id UUID PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        workflow_id TEXT,
        workflow_version TEXT,
        status TEXT NOT NULL,
        schema_version INTEGER NOT NULL DEFAULT 1,
        state JSONB NOT NULL,
        state_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ois_checkpoints_tenant
        ON ois_execution_checkpoints (tenant_id, updated_at DESC);
    CREATE TABLE IF NOT EXISTS ois_execution_checkpoint_history (
        checkpoint_id UUID PRIMARY KEY,
        execution_id UUID NOT NULL,
        tenant_id TEXT NOT NULL,
        workflow_id TEXT,
        workflow_version TEXT,
        step_index INTEGER NOT NULL,
        status TEXT NOT NULL,
        schema_version INTEGER NOT NULL DEFAULT 1,
        state JSONB NOT NULL,
        state_hash TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_ois_checkpoint_history_execution
        ON ois_execution_checkpoint_history
        (tenant_id, execution_id, step_index DESC, created_at DESC);
    CREATE OR REPLACE FUNCTION ois_reject_checkpoint_history_mutation()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'OIS checkpoint history is immutable';
    END;
    $$;
    DROP TRIGGER IF EXISTS trg_ois_checkpoint_history_immutable
        ON ois_execution_checkpoint_history;
    CREATE TRIGGER trg_ois_checkpoint_history_immutable
        BEFORE UPDATE OR DELETE ON ois_execution_checkpoint_history
        FOR EACH ROW EXECUTE FUNCTION ois_reject_checkpoint_history_mutation();
    CREATE TABLE IF NOT EXISTS ois_idempotency_results (
        invocation_id TEXT PRIMARY KEY,
        execution_id UUID NOT NULL,
        tenant_id TEXT NOT NULL,
        capability_id TEXT NOT NULL,
        status TEXT NOT NULL,
        result JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS ois_side_effect_outbox (
        effect_id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        execution_id UUID NOT NULL,
        invocation_id TEXT NOT NULL UNIQUE,
        capability_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL UNIQUE,
        request JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        attempts INTEGER NOT NULL DEFAULT 0,
        locked_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        result JSONB,
        last_error JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_ois_outbox_pending
        ON ois_side_effect_outbox (status, created_at);
    """

    def __init__(self, dsn: str | Callable[[], Any]) -> None:
        if psycopg is None:
            raise PostgresConfigurationError(
                "psycopg is required for PostgresDurableExecutionStore"
            )
        self._connect = (lambda: psycopg.connect(dsn)) if isinstance(dsn, str) else dsn

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(self.SCHEMA)
            connection.commit()

    @staticmethod
    def _state_payload(context: ExecutionContext) -> tuple[str, str]:
        payload = json.dumps(context.to_dict(), sort_keys=True, separators=(",", ":"))
        return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _checkpoint_sql() -> str:
        return """
            INSERT INTO ois_execution_checkpoints (
                execution_id, tenant_id, workflow_id, workflow_version,
                status, schema_version, state, state_hash, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 1, %s::jsonb, %s, %s, %s)
            ON CONFLICT (execution_id) DO UPDATE SET
                tenant_id = EXCLUDED.tenant_id,
                workflow_id = EXCLUDED.workflow_id,
                workflow_version = EXCLUDED.workflow_version,
                status = EXCLUDED.status,
                schema_version = EXCLUDED.schema_version,
                state = EXCLUDED.state,
                state_hash = EXCLUDED.state_hash,
                updated_at = EXCLUDED.updated_at
        """

    def save(self, context: ExecutionContext) -> None:
        """Persist current state and append an immutable checkpoint in one transaction."""
        self._save_with_history(context, UUID(str(UUID(int=0))))

    def save_checkpoint(self, checkpoint_id: UUID, context: ExecutionContext) -> None:
        """Persist current state and an immutable, content-addressed checkpoint."""
        self._save_with_history(context, checkpoint_id)

    def _save_with_history(self, context: ExecutionContext, checkpoint_id: UUID) -> None:
        context.touch()
        payload, digest = self._state_payload(context)
        step_index = int(context.metadata.get("step_index", context.retry_count))
        if checkpoint_id.int == 0:
            checkpoint_id = UUID(
                hashlib.sha256(
                    f"{context.identity.execution_id}:{context.updated_at.isoformat()}".encode()
                ).hexdigest()[:32]
            )
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    self._checkpoint_sql(),
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
                    INSERT INTO ois_execution_checkpoint_history (
                        checkpoint_id, execution_id, tenant_id, workflow_id,
                        workflow_version, step_index, status, schema_version,
                        state, state_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s::jsonb, %s, %s)
                    ON CONFLICT (checkpoint_id) DO NOTHING
                    """,
                    (
                        checkpoint_id,
                        context.identity.execution_id,
                        context.identity.tenant_id,
                        context.identity.workflow_id,
                        context.identity.workflow_version,
                        step_index,
                        context.status.value,
                        payload,
                        digest,
                        context.updated_at,
                    ),
                )
            connection.commit()

    def fetch_last_valid_checkpoint(
        self, execution_id: UUID, *, tenant_id: str = "default"
    ) -> ExecutionContext | None:
        """Recover the newest integrity- and schema-valid historical snapshot."""
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT state, state_hash
                FROM ois_execution_checkpoint_history
                WHERE tenant_id = %s AND execution_id = %s
                ORDER BY step_index DESC, created_at DESC
                """,
                (tenant_id, execution_id),
            )
            rows = cursor.fetchall()
        for state, expected_hash in rows:
            if isinstance(state, str):
                state = json.loads(state)
            canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != expected_hash:
                continue
            try:
                return ExecutionContext.from_dict(state)
            except (TypeError, ValueError, KeyError):
                continue
        return None

    def commit_checkpoint_and_side_effect(
        self,
        context: ExecutionContext,
        command: SideEffectCommand,
    ) -> None:
        """Atomically persist execution state and its side-effect intent."""
        context.touch()
        payload, digest = self._state_payload(context)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    self._checkpoint_sql(),
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

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                ("SELECT state, state_hash FROM ois_execution_checkpoints WHERE execution_id = %s"),
                (execution_id,),
            )
            row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No PostgreSQL checkpoint for execution {execution_id}")
        state = row[0]
        if isinstance(state, str):
            state = json.loads(state)
        canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
        actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_hash != row[1]:
            raise ValueError(f"Checkpoint integrity failure for execution {execution_id}")
        return ExecutionContext.from_dict(state)

    def delete(self, execution_id: UUID) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM ois_execution_checkpoints WHERE execution_id = %s",
                    (execution_id,),
                )
            connection.commit()

    def get_idempotency(self, invocation_id: str) -> InvocationResult | None:
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT result FROM ois_idempotency_results WHERE invocation_id = %s",
                (invocation_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        data: Mapping[str, Any] = row[0]
        return InvocationResult(
            invocation_id=str(data["invocation_id"]),
            capability_id=str(data["capability_id"]),
            status=InvocationStatus(data["status"]),
            output=data.get("output"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )

    def put_idempotency(
        self,
        invocation_id: str,
        execution_id: UUID,
        tenant_id: str,
        result: InvocationResult,
    ) -> None:
        if result.status not in {InvocationStatus.SUCCEEDED, InvocationStatus.CANCELLED}:
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
        with self.connection() as connection:
            with connection.cursor() as cursor:
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

    def close(self) -> None:
        """Compatibility hook for stores that own a pool externally."""
        return None
