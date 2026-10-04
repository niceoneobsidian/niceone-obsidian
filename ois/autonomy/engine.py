"""Unified durable autonomous execution engine (Phase D6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import UUID

from ois.infrastructure.postgres_fencing import PostgresWorkerLeaseStore, WorkerLease

from .approvals import ApprovalDecision, ApprovalRequest
from .durable import (
    DurableRunStatus,
    DurableWorkflowRun,
    FencedPostgresWorkflowRunRepository,
    PostgresWorkflowRunRepository,
)
from .durable_approvals import FencedApprovalResume, PostgresApprovalStore
from .events import EventEnvelope
from .policy import AutomationPolicy, PolicyOutcome
from .side_effects import PostgresSideEffectLedger, SideEffectLedgerEntry
from .workflows import SourceWorkflow


@dataclass(frozen=True)
class DurableExecutionReceipt:
    run: DurableWorkflowRun
    approval_id: str | None = None
    resumed: bool = False


class DurableAutonomousExecutionEngine:
    """Production boundary joining policy, approvals, durability, and fencing.

    The engine never calls provider APIs itself. Execution remains a Kernel-owned
    action/capability boundary supplied by the caller.
    """

    def __init__(
        self,
        *,
        runs: PostgresWorkflowRunRepository,
        leases: PostgresWorkerLeaseStore,
        approvals: PostgresApprovalStore,
        side_effects: PostgresSideEffectLedger,
        policy: AutomationPolicy,
    ) -> None:
        self.runs = runs
        self.leases = leases
        self.approvals = approvals
        self.side_effects = side_effects
        self.policy = policy

    def start(
        self,
        *,
        workflow: SourceWorkflow,
        event: EventEnvelope,
        worker_id: str,
        execute: Callable[[SourceWorkflow, EventEnvelope], Any],
    ) -> DurableExecutionReceipt:
        if not workflow.matches(event):
            raise ValueError("workflow trigger did not match event")
        run = self.runs.create(
            DurableWorkflowRun.new(
                tenant_id=event.tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=workflow.workflow_id,
                workflow_version=workflow.version,
                event_id=event.event_id,
            )
        )
        if not self.runs.claim_idempotency(run):
            existing = self.runs.get_by_event(
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_id=run.workflow_id,
                workflow_version=run.workflow_version,
                event_id=run.event_id,
            )
            if existing is None:
                raise RuntimeError("idempotency claim lost without an existing workflow run")
            return DurableExecutionReceipt(existing)

        lease = self.leases.claim(run.run_id, worker_id)
        if lease is None:
            return DurableExecutionReceipt(run)
        return self._execute(run, workflow, event, lease, execute)

    def resume_approval(
        self,
        *,
        approval_id: str,
        worker_id: str,
        execute: Callable[[SourceWorkflow, EventEnvelope], Any],
        workflow: SourceWorkflow,
    ) -> DurableExecutionReceipt:
        approval = self.approvals.get(approval_id)
        if approval is None:
            raise KeyError("approval not found")
        if approval.decision != ApprovalDecision.APPROVED:
            raise ValueError("approval is not approved")
        run = self.runs.get_by_event(
            tenant_id=approval.tenant_id,
            workspace_id=approval.workspace_id,
            workflow_id=approval.workflow_id,
            workflow_version=workflow.version,
            event_id=approval.event_id,
        )
        if run is None:
            raise KeyError("workflow run for approval not found")
        lease = self.leases.claim(run.run_id, worker_id)
        if lease is None:
            raise RuntimeError("workflow run is owned by another worker")
        event = FencedApprovalResume(self.approvals, self.leases, lease).resume_event(
            approval_id
        )
        return self._execute(run, workflow, event, lease, execute)

    def _execute(
        self,
        run: DurableWorkflowRun,
        workflow: SourceWorkflow,
        event: EventEnvelope,
        lease: WorkerLease,
        execute: Callable[[SourceWorkflow, EventEnvelope], Any],
    ) -> DurableExecutionReceipt:
        fenced = FencedPostgresWorkflowRunRepository(self.runs, self.leases, lease)
        evaluation = self.policy.evaluate({**event.payload, "event_type": event.event_type})

        if evaluation.outcome == PolicyOutcome.DENY:
            stopped = fenced.transition(run.run_id, status=DurableRunStatus.STOPPED)
            self.leases.release(lease)
            return DurableExecutionReceipt(stopped)

        if evaluation.outcome == PolicyOutcome.APPROVAL_REQUIRED:
            approval = self.approvals.get_by_event(run.event_id)
            if approval is None:
                now = datetime.now(UTC)
                approval = self.approvals.create(
                    ApprovalRequest(
                        approval_id=str(run.run_id),
                        tenant_id=run.tenant_id,
                        workspace_id=run.workspace_id,
                        workflow_id=run.workflow_id,
                        event_id=run.event_id,
                        reason=evaluation.reason,
                        created_at=now,
                        expires_at=now + timedelta(hours=1),
                        event=event,
                    ),
                    run_id=run.run_id,
                )
            waiting = fenced.transition(
                run.run_id,
                status=DurableRunStatus.WAITING_APPROVAL,
                checkpoint={"phase": "approval", "approval_id": approval.approval_id},
            )
            self.leases.release(lease)
            return DurableExecutionReceipt(waiting, approval.approval_id)

        running = fenced.transition(
            run.run_id,
            status=DurableRunStatus.RUNNING,
            checkpoint={"phase": "execution", "event_id": event.event_id},
        )
        try:
            result = execute(workflow, event)
        except Exception as exc:
            failed = fenced.transition(
                run.run_id,
                status=DurableRunStatus.RECOVERING,
                attempt=running.attempt + 1,
                checkpoint={"phase": "recovery", "event_id": event.event_id},
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            self.leases.release(lease)
            return DurableExecutionReceipt(failed)

        completed = fenced.transition(
            run.run_id,
            status=DurableRunStatus.COMPLETED,
            checkpoint={"phase": "completed", "event_id": event.event_id},
            result=result,
        )
        self.leases.release(lease)
        return DurableExecutionReceipt(completed)

    def prepare_side_effect(
        self,
        *,
        lease: WorkerLease,
        tenant_id: str,
        workspace_id: str,
        run_id: UUID,
        invocation_id: str,
        idempotency_key: str,
        capability_id: str,
        request: dict[str, Any],
    ) -> SideEffectLedgerEntry:
        self.leases.assert_current(lease)
        return self.side_effects.prepare(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            run_id=run_id,
            invocation_id=invocation_id,
            idempotency_key=idempotency_key,
            capability_id=capability_id,
            request=request,
        )
