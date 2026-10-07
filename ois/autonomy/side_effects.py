"""Durable side-effect ledger for autonomous execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SideEffectLedgerEntry:
    effect_id: UUID
    tenant_id: str
    workspace_id: str
    run_id: UUID
    invocation_id: str
    idempotency_key: str
    capability_id: str
    request: dict[str, Any]
    status: str
    result: Any = None
    error: dict[str, Any] | None = None
    completed_at: datetime | None = None


class PostgresSideEffectLedger:
    """Prepare and complete side effects exactly once by idempotency key."""

    def __init__(self, connection_factory: Any) -> None:
        self._connect = connection_factory

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def prepare(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        run_id: UUID,
        invocation_id: str,
        idempotency_key: str,
        capability_id: str,
        request: dict[str, Any],
    ) -> SideEffectLedgerEntry:
        effect_id = uuid4()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO autonomous_side_effect_ledger
                   (effect_id, tenant_id, workspace_id, run_id, invocation_id,
                    idempotency_key, capability_id, request)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (idempotency_key) DO NOTHING
                   RETURNING effect_id, status""",
                (
                    effect_id,
                    tenant_id,
                    workspace_id,
                    run_id,
                    invocation_id,
                    idempotency_key,
                    capability_id,
                    self._json(request),
                ),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """SELECT effect_id, tenant_id, workspace_id, run_id, invocation_id,
                              idempotency_key, capability_id, request, status, result, error,
                              completed_at
                       FROM autonomous_side_effect_ledger
                       WHERE idempotency_key = %s""",
                    (idempotency_key,),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise RuntimeError("side-effect ledger entry disappeared")
        return self._row(row)

    def complete(self, idempotency_key: str, *, result: Any) -> SideEffectLedgerEntry:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE autonomous_side_effect_ledger
                   SET status = 'completed', result = %s::jsonb,
                       completed_at = COALESCE(completed_at, now())
                   WHERE idempotency_key = %s AND status <> 'completed'
                   RETURNING effect_id, tenant_id, workspace_id, run_id, invocation_id,
                             idempotency_key, capability_id, request, status, result, error,
                             completed_at""",
                (self._json(result), idempotency_key),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    """SELECT effect_id, tenant_id, workspace_id, run_id, invocation_id,
                              idempotency_key, capability_id, request, status, result, error,
                              completed_at
                       FROM autonomous_side_effect_ledger WHERE idempotency_key = %s""",
                    (idempotency_key,),
                )
                row = cursor.fetchone()
            connection.commit()
        if row is None:
            raise KeyError(f"side-effect not found: {idempotency_key}")
        return self._row(row)

    def get(self, idempotency_key: str) -> SideEffectLedgerEntry | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT effect_id, tenant_id, workspace_id, run_id, invocation_id,
                          idempotency_key, capability_id, request, status, result, error,
                          completed_at
                   FROM autonomous_side_effect_ledger WHERE idempotency_key = %s""",
                (idempotency_key,),
            )
            row = cursor.fetchone()
        return self._row(row) if row else None

    @staticmethod
    def _row(row: tuple[Any, ...]) -> SideEffectLedgerEntry:
        def decode(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        return SideEffectLedgerEntry(
            effect_id=UUID(str(row[0])),
            tenant_id=str(row[1]),
            workspace_id=str(row[2]),
            run_id=UUID(str(row[3])),
            invocation_id=str(row[4]),
            idempotency_key=str(row[5]),
            capability_id=str(row[6]),
            request=dict(decode(row[7])),
            status=str(row[8]),
            result=decode(row[9]) if row[9] is not None else None,
            error=decode(row[10]) if row[10] is not None else None,
            completed_at=row[11],
        )
