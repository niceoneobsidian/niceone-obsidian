"""Durable Phase D workflow-run state and idempotency repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class DurableRunStatus(StrEnum):
    RECEIVED = "received"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class DurableWorkflowRun:
    run_id: UUID
    tenant_id: str
    workspace_id: str
    workflow_id: str
    workflow_version: str
    event_id: str
    status: DurableRunStatus
    attempt: int = 0
    checkpoint: dict[str, Any] | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    idempotency_key: str = ""

    @classmethod
    def new(
        cls,
        *,
        tenant_id: str,
        workspace_id: str,
        workflow_id: str,
        workflow_version: str,
        event_id: str,
        idempotency_key: str | None = None,
    ) -> DurableWorkflowRun:
        return cls(
            run_id=uuid4(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_id=event_id,
            status=DurableRunStatus.RECEIVED,
            idempotency_key=idempotency_key or (
                f"{tenant_id}:{workspace_id}:{workflow_id}:{workflow_version}:{event_id}"
            ),
        )


class PostgresWorkflowRunRepository:
    """PostgreSQL system-of-record for autonomous workflow runs.

    Every mutating operation is scoped by tenant/workspace and keyed by the
    immutable workflow/event identity.  Idempotency claims are durable and
    survive process restarts.
    """

    def __init__(self, connection_factory: Any) -> None:
        self._connect = connection_factory

    @staticmethod
    def _payload(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def create(self, run: DurableWorkflowRun) -> DurableWorkflowRun:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO autonomous_workflow_runs (
                    run_id, tenant_id, workspace_id, workflow_id,
                    workflow_version, event_id, status, result, error,
                    attempt, checkpoint, idempotency_key, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL,
                          %s, %s::jsonb, %s, now())
                ON CONFLICT (tenant_id, workspace_id, workflow_id, workflow_version, event_id)
                DO NOTHING
                RETURNING run_id
                """,
                (
                    run.run_id, run.tenant_id, run.workspace_id, run.workflow_id,
                    run.workflow_version, run.event_id, run.status.value,
                    run.attempt, self._payload(run.checkpoint or {}),
                    run.idempotency_key,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
        if row is None:
            existing = self.get_by_event(
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_id=run.workflow_id,
                workflow_version=run.workflow_version,
                event_id=run.event_id,
            )
            if existing is None:
                raise RuntimeError("workflow run insert conflicted but existing run was not found")
            return existing
        return run

    def get(self, run_id: UUID) -> DurableWorkflowRun | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT run_id, tenant_id, workspace_id, workflow_id, workflow_version,
                          event_id, status, attempt, checkpoint, result, error, idempotency_key
                   FROM autonomous_workflow_runs
                   WHERE run_id = %s""",
                (run_id,),
            )
            row = cursor.fetchone()
        return self._row(row) if row else None

    def get_by_event(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        workflow_id: str,
        workflow_version: str,
        event_id: str,
    ) -> DurableWorkflowRun | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT run_id, tenant_id, workspace_id, workflow_id, workflow_version,
                          event_id, status, attempt, checkpoint, result, error, idempotency_key
                   FROM autonomous_workflow_runs
                   WHERE tenant_id = %s AND workspace_id = %s AND workflow_id = %s
                     AND workflow_version = %s AND event_id = %s""",
                (tenant_id, workspace_id, workflow_id, workflow_version, event_id),
            )
            row = cursor.fetchone()
        return self._row(row) if row else None

    def transition(
        self,
        run_id: UUID,
        *,
        status: DurableRunStatus,
        attempt: int | None = None,
        checkpoint: dict[str, Any] | None = None,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> DurableWorkflowRun:
        updates = ["status = %s", "updated_at = now()"]
        params: list[Any] = [status.value]
        if attempt is not None:
            updates.append("attempt = %s")
            params.append(attempt)
        if checkpoint is not None:
            updates.append("checkpoint = %s::jsonb")
            params.append(self._payload(checkpoint))
        if result is not None:
            updates.append("result = %s::jsonb")
            params.append(self._payload(result))
        if error is not None:
            updates.append("error = %s::jsonb")
            params.append(self._payload(error))
        params.append(run_id)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""UPDATE autonomous_workflow_runs SET {", ".join(updates)}
                    WHERE run_id = %s RETURNING run_id, tenant_id, workspace_id, workflow_id,
                    workflow_version, event_id, status, attempt, checkpoint, result, error,
                    idempotency_key""",
                params,
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"workflow run not found: {run_id}")
            connection.commit()
        return self._row(row)

    def claim_idempotency(self, run: DurableWorkflowRun) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO autonomous_workflow_idempotency
                   (idempotency_key, tenant_id, workspace_id, run_id)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (idempotency_key) DO NOTHING""",
                (run.idempotency_key, run.tenant_id, run.workspace_id, run.run_id),
            )
            claimed = cursor.rowcount == 1
            connection.commit()
        return claimed

    @staticmethod
    def _row(row: tuple[Any, ...]) -> DurableWorkflowRun:
        checkpoint = row[8]
        result = row[9]
        error = row[10]
        return DurableWorkflowRun(
            run_id=UUID(str(row[0])),
            tenant_id=str(row[1]),
            workspace_id=str(row[2]),
            workflow_id=str(row[3]),
            workflow_version=str(row[4]),
            event_id=str(row[5]),
            status=DurableRunStatus(str(row[6])),
            attempt=int(row[7]),
            checkpoint=checkpoint if isinstance(checkpoint, dict) else json.loads(checkpoint or "{}"),
            result=result if not isinstance(result, str) else json.loads(result),
            error=error if not isinstance(error, str) else json.loads(error),
            idempotency_key=str(row[11]),
        )
