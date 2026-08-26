from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

from .checkpoint import CheckpointError, CheckpointNotFound, CheckpointStore
from .state import ExecutionContext


class PostgreSQLCheckpointStoreError(CheckpointError):
    """Raised when PostgreSQL checkpoint persistence fails."""


class PostgreSQLCheckpointStore(CheckpointStore):
    """PostgreSQL-backed authoritative execution checkpoint store.

    The store keeps one current checkpoint per execution. Writes are atomic
    through PostgreSQL's INSERT ... ON CONFLICT update, so a worker crash
    cannot leave a partially written JSON document behind.

    ``connection_factory`` must return a psycopg connection. Keeping the
    factory injectable makes connection pooling and application lifecycle
    management the responsibility of the control/runtime layer.
    """

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def initialize(self) -> None:
        """Create the checkpoint table if it does not already exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS ois_execution_checkpoints (
            execution_id UUID PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            workflow_id TEXT,
            workflow_version TEXT,
            status TEXT NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                connection.commit()
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise PostgreSQLCheckpointStoreError(
                "Failed to initialize PostgreSQL checkpoint storage"
            ) from exc

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        payload = context.to_dict()
        identity = context.identity
        sql = """
        INSERT INTO ois_execution_checkpoints (
            execution_id, tenant_id, workflow_id, workflow_version,
            status, payload, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (execution_id) DO UPDATE SET
            tenant_id = EXCLUDED.tenant_id,
            workflow_id = EXCLUDED.workflow_id,
            workflow_version = EXCLUDED.workflow_version,
            status = EXCLUDED.status,
            payload = EXCLUDED.payload,
            updated_at = EXCLUDED.updated_at
        """
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql,
                        (
                            identity.execution_id,
                            identity.tenant_id,
                            identity.workflow_id,
                            identity.workflow_version,
                            context.status.value,
                            json.dumps(payload),
                            context.created_at,
                            context.updated_at,
                        ),
                    )
                connection.commit()
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise PostgreSQLCheckpointStoreError(
                f"Failed to save checkpoint for execution {identity.execution_id}"
            ) from exc

    def load(self, execution_id: UUID) -> ExecutionContext:
        sql = """
        SELECT payload
        FROM ois_execution_checkpoints
        WHERE execution_id = %s
        """
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, (execution_id,))
                    row = cursor.fetchone()
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise PostgreSQLCheckpointStoreError(
                f"Failed to load checkpoint for execution {execution_id}"
            ) from exc

        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")

        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise PostgreSQLCheckpointStoreError(
                f"Invalid checkpoint payload for execution {execution_id}"
            )
        return ExecutionContext.from_dict(payload)

    def delete(self, execution_id: UUID) -> None:
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM ois_execution_checkpoints WHERE execution_id = %s",
                        (execution_id,),
                    )
                connection.commit()
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise PostgreSQLCheckpointStoreError(
                f"Failed to delete checkpoint for execution {execution_id}"
            ) from exc

    def exists(self, execution_id: UUID) -> bool:
        try:
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT 1 FROM ois_execution_checkpoints WHERE execution_id = %s",
                        (execution_id,),
                    )
                    return cursor.fetchone() is not None
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise PostgreSQLCheckpointStoreError(
                f"Failed to check checkpoint for execution {execution_id}"
            ) from exc
