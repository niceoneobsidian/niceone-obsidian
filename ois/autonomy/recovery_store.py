"""Crash-safe workflow checkpointing and recovery sweeper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .durable import DurableRunStatus, DurableWorkflowRun, PostgresWorkflowRunRepository


@dataclass(frozen=True)
class RecoveryCandidate:
    run_id: UUID
    recovery_count: int


class WorkflowRecoverySweeper:
    """Find abandoned runs and move them to a durable recovery state."""

    def __init__(
        self,
        repository: PostgresWorkflowRunRepository,
        *,
        stale_after_seconds: int = 300,
        max_recoveries: int = 3,
    ) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if max_recoveries < 1:
            raise ValueError("max_recoveries must be positive")
        self._repository = repository
        self._stale_after_seconds = stale_after_seconds
        self._max_recoveries = max_recoveries

    def sweep(self, *, limit: int = 100) -> tuple[DurableWorkflowRun, ...]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._repository._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT run_id
                   FROM autonomous_workflow_runs
                   WHERE status IN ('running', 'recovering')
                     AND last_heartbeat_at < now() - (%s * interval '1 second')
                     AND recovery_count < %s
                   ORDER BY last_heartbeat_at
                   FOR UPDATE SKIP LOCKED
                   LIMIT %s""",
                (self._stale_after_seconds, self._max_recoveries, limit),
            )
            run_ids = [UUID(str(row[0])) for row in cursor.fetchall()]
            recovered: list[DurableWorkflowRun] = []
            for run_id in run_ids:
                cursor.execute(
                    """UPDATE autonomous_workflow_runs
                       SET status = %s, recovery_count = recovery_count + 1,
                           next_attempt_at = now(), last_heartbeat_at = now(),
                           updated_at = now()
                       WHERE run_id = %s
                       RETURNING run_id, tenant_id, workspace_id, workflow_id,
                       workflow_version, event_id, status, attempt, checkpoint,
                       result, error, idempotency_key""",
                    (DurableRunStatus.RECOVERING.value, run_id),
                )
                row = cursor.fetchone()
                if row is not None:
                    recovered.append(self._repository._row(row))
            connection.commit()
        return tuple(recovered)

    def resume(self, run_id: UUID) -> dict[str, Any]:
        run = self._repository.get(run_id)
        if run is None:
            raise KeyError(f"workflow run not found: {run_id}")
        if run.status not in {DurableRunStatus.RECOVERING, DurableRunStatus.RUNNING}:
            raise ValueError(f"workflow run is not resumable: {run.status.value}")
        return dict(run.checkpoint or {})
