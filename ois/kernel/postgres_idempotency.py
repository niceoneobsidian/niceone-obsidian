from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .contracts import InvocationResult
from .idempotency import IdempotencyStore
from .types import InvocationStatus


class PostgreSQLIdempotencyStore(IdempotencyStore):
    """PostgreSQL-backed idempotency records that survive worker restarts."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def initialize(self) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ois_idempotency_results (
                        invocation_id TEXT PRIMARY KEY,
                        result_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            connection.commit()

    def get(self, invocation_id: str) -> InvocationResult | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT result_json FROM ois_idempotency_results WHERE invocation_id = %s",
                    (invocation_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return InvocationResult(
            invocation_id=payload["invocation_id"],
            capability_id=payload["capability_id"],
            status=InvocationStatus(payload["status"]),
            output=payload.get("output"),
            error=payload.get("error"),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            metadata=payload.get("metadata", {}),
        )

    def put(self, invocation_id: str, result: InvocationResult) -> None:
        payload = json.dumps(
            {
                "invocation_id": result.invocation_id,
                "capability_id": result.capability_id,
                "status": result.status.value,
                "output": result.output,
                "error": result.error,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "metadata": dict(result.metadata),
            },
            sort_keys=True,
        )
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ois_idempotency_results (invocation_id, result_json)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (invocation_id) DO NOTHING
                    """,
                    (invocation_id, payload),
                )
            connection.commit()

    def exists(self, invocation_id: str) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM ois_idempotency_results WHERE invocation_id = %s",
                    (invocation_id,),
                )
                return cursor.fetchone() is not None
