"""PostgreSQL-backed human approval state for autonomous workflows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ois.infrastructure.postgres_fencing import PostgresWorkerLeaseStore, WorkerLease

from .approvals import ApprovalDecision, ApprovalRequest
from .events import EventEnvelope


class PostgresApprovalStore:
    """Persistent approval store with expiry and original-event preservation."""

    def __init__(self, connection_factory: Any) -> None:
        self._connect = connection_factory

    @staticmethod
    def _event_payload(event: EventEnvelope | None) -> str:
        return json.dumps(dict(event.payload) if event else {}, sort_keys=True)

    def create(self, request: ApprovalRequest, *, run_id: UUID | None = None) -> ApprovalRequest:
        event = request.event
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO autonomous_approvals
                   (approval_id, tenant_id, workspace_id, workflow_id, event_id, reason,
                    decision, created_at, expires_at, run_id, event_payload, source_id, event_type)
                   VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s::jsonb, %s, %s)
                   """,
                (
                    request.approval_id,
                    request.tenant_id,
                    request.workspace_id,
                    request.workflow_id,
                    request.event_id,
                    request.reason,
                    request.created_at,
                    request.expires_at,
                    run_id,
                    self._event_payload(event),
                    event.source_id if event else None,
                    event.event_type if event else None,
                ),
            )
            connection.commit()
        return request

    def get(self, approval_id: str) -> ApprovalRequest | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT approval_id, tenant_id, workspace_id, workflow_id, event_id,
                          reason, decision, created_at, expires_at, decided_by, decided_at,
                          event_payload, source_id, event_type
                   FROM autonomous_approvals WHERE approval_id = %s""",
                (approval_id,),
            )
            row = cursor.fetchone()
        return self._row(row) if row else None

    def get_by_event(self, event_id: str) -> ApprovalRequest | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT approval_id, tenant_id, workspace_id, workflow_id, event_id,
                          reason, decision, created_at, expires_at, decided_by, decided_at,
                          event_payload, source_id, event_type
                   FROM autonomous_approvals
                   WHERE event_id = %s AND decision = 'pending'
                   ORDER BY created_at DESC LIMIT 1""",
                (event_id,),
            )
            row = cursor.fetchone()
        return self._row(row) if row else None

    def decide(self, approval_id: str, decision: ApprovalDecision, actor: str) -> ApprovalRequest:
        now = datetime.now(UTC)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE autonomous_approvals
                   SET decision = %s, decided_by = %s, decided_at = %s
                   WHERE approval_id = %s
                     AND decision = 'pending' AND expires_at > %s
                   RETURNING approval_id, tenant_id, workspace_id, workflow_id, event_id,
                             reason, decision, created_at, expires_at, decided_by, decided_at,
                             event_payload, source_id, event_type""",
                (decision.value, actor, now, approval_id, now),
            )
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "UPDATE autonomous_approvals SET decision = 'expired' "
                    "WHERE approval_id = %s AND decision = 'pending' AND expires_at <= %s",
                    (approval_id, now),
                )
                connection.commit()
                raise ValueError("approval is missing, already decided, or expired")
            connection.commit()
        return self._row(row)

    def resume_event(self, approval_id: str) -> EventEnvelope:
        request = self.get(approval_id)
        if request is None:
            raise KeyError("approval not found")
        if request.decision != ApprovalDecision.APPROVED:
            raise ValueError("approval is not approved")
        if request.event is not None:
            return request.event
        return EventEnvelope(
            event_id=request.event_id,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            event_type="approval.resumed",
            aggregate_id=request.event_id,
        )

    @staticmethod
    def _row(row: tuple[Any, ...]) -> ApprovalRequest:
        payload = row[11] if isinstance(row[11], dict) else json.loads(row[11] or "{}")
        event = None
        if row[13] is not None:
            event = EventEnvelope(
                event_id=str(row[4]),
                tenant_id=str(row[1]),
                workspace_id=str(row[2]),
                event_type=str(row[13]),
                aggregate_id=str(row[4]),
                source_id=str(row[12]) if row[12] is not None else None,
                payload=payload,
            )
        return ApprovalRequest(
            approval_id=str(row[0]),
            tenant_id=str(row[1]),
            workspace_id=str(row[2]),
            workflow_id=str(row[3]),
            event_id=str(row[4]),
            reason=str(row[5]),
            decision=ApprovalDecision(str(row[6])),
            created_at=row[7],
            expires_at=row[8],
            decided_by=row[9],
            decided_at=row[10],
            event=event,
        )


class FencedApprovalResume:
    """Require current worker ownership before resuming an approved run."""

    def __init__(
        self,
        store: PostgresApprovalStore,
        lease_store: PostgresWorkerLeaseStore,
        lease: WorkerLease,
    ) -> None:
        self._store = store
        self._lease_store = lease_store
        self.lease = lease

    def resume_event(self, approval_id: str) -> EventEnvelope:
        with self._store._connect() as connection, connection.cursor() as cursor:
            self._lease_store._assert_current_cursor(cursor, self.lease)
        return self._store.resume_event(approval_id)
