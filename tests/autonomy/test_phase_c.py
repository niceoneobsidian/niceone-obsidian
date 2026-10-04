from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ois.autonomy import (
    ApprovalDecision,
    ApprovalGate,
    AutonomousLoop,
    AutonomousOperations,
    EventEnvelope,
    FailureRecovery,
    InMemoryApprovalStore,
    AutomationPolicy,
    PolicyRule,
    SourceWorkflow,
    WorkflowTrigger,
)


def event(*, event_type: str = "source.updated", payload: dict[str, object] | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id="evt-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        event_type=event_type,
        aggregate_id="record-1",
        source_id="github",
        payload=payload or {"risk_level": "low"},
    )


def workflow(action, *, event_type: str = "source.updated") -> SourceWorkflow:
    return SourceWorkflow(
        workflow_id="wf-1",
        version="1.0.0",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        trigger=WorkflowTrigger(event_type=event_type, source_id="github"),
        action=action,
    )


def allow_policy() -> AutomationPolicy:
    return AutomationPolicy((PolicyRule(rule_id="allow", event_type="source.updated"),))


def test_source_event_triggers_workflow_once() -> None:
    calls: list[str] = []
    operations = AutonomousOperations(policy=allow_policy())
    operations.register_workflow(workflow(lambda evt: calls.append(evt.event_id)))

    first = operations.route(event())
    second = operations.route(event())

    assert first.workflow_ids == ("wf-1",)
    assert first.decisions[0].workflow_run is not None
    assert second.decisions[0].reason == "workflow event already processed"
    assert calls == ["evt-1"]


def test_event_router_preserves_tenant_workflow_scope() -> None:
    calls: list[str] = []
    operations = AutonomousOperations(policy=allow_policy())
    operations.register_workflow(workflow(lambda evt: calls.append(evt.tenant_id)))

    other_tenant = EventEnvelope(
        event_id="evt-2",
        tenant_id="tenant-2",
        workspace_id="workspace-1",
        event_type="source.updated",
        aggregate_id="record-1",
        source_id="github",
        payload={"risk_level": "low", "source_id": "github"},
    )
    receipt = operations.route(other_tenant)

    assert receipt.workflow_ids == ()
    assert calls == []


def test_policy_denies_unmatched_event_without_execution() -> None:
    calls: list[str] = []
    operations = AutonomousOperations(
        policy=AutomationPolicy((PolicyRule(rule_id="github-only", event_type="github.updated"),))
    )
    operations.register_workflow(workflow(lambda evt: calls.append(evt.event_id)))

    receipt = operations.route(event())

    assert receipt.decisions[0].state.value == "stopped"
    assert calls == []


def test_high_risk_workflow_waits_for_human_approval() -> None:
    calls: list[str] = []
    operations = AutonomousOperations(
        policy=AutomationPolicy((PolicyRule(rule_id="allow", event_type="source.updated"),))
    )
    wf = workflow(lambda evt: calls.append(evt.event_id))
    operations.register_workflow(wf)

    high_risk = event(payload={"risk_level": "high", "requires_approval": True})
    receipt = operations.route(high_risk)

    decision = receipt.decisions[0]
    assert decision.state.value == "waiting_approval"
    assert decision.approval_id is not None
    assert calls == []

    resumed = operations.approve_and_resume(decision.approval_id, "operator-1")
    assert resumed.state.value == "idle"
    assert calls == ["evt-1"]


def test_rejected_approval_cannot_be_reused() -> None:
    store = InMemoryApprovalStore()
    gate = ApprovalGate(store, ttl_seconds=60)
    request = gate.request(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        workflow_id="wf-1",
        event_id="evt-1",
        reason="high risk",
    )

    decided = store.decide(request.approval_id, ApprovalDecision.REJECTED, "operator-1")
    assert decided.decision == ApprovalDecision.REJECTED

    with pytest.raises(ValueError, match="already decided"):
        store.decide(request.approval_id, ApprovalDecision.APPROVED, "operator-2")


def test_expired_approval_is_rejected() -> None:
    store = InMemoryApprovalStore()
    now = datetime.now(UTC)
    from ois.autonomy.approvals import ApprovalRequest

    store.create(
        ApprovalRequest(
            approval_id="approval-1",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            workflow_id="wf-1",
            event_id="evt-1",
            reason="high risk",
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(seconds=1),
        )
    )

    with pytest.raises(ValueError, match="expired"):
        store.decide("approval-1", ApprovalDecision.APPROVED, "operator-1")


def test_failure_recovery_is_bounded_and_safe() -> None:
    recovery = FailureRecovery(max_retries=2)

    assert recovery.decide(attempt=1, failure="transient").action.value == "retry"
    assert recovery.decide(attempt=3, failure="transient").action.value == "escalate"
    assert recovery.decide(attempt=1, failure="safety").action.value == "stop"
    assert recovery.decide(attempt=1, failure="permission").action.value == "escalate"


def test_autonomous_loop_stops_after_recovery_bound() -> None:
    calls = 0

    def fail(_event):
        nonlocal calls
        calls += 1
        raise RuntimeError("temporary upstream failure")

    loop = AutonomousLoop(
        policy=allow_policy(),
        approval_gate=ApprovalGate(InMemoryApprovalStore()),
        recovery=FailureRecovery(max_retries=1),
        max_iterations=2,
    )
    decision = loop.run(workflow=workflow(fail), event=event())

    assert decision.state.value == "recovering"
    assert calls == 2


def test_outbox_events_can_drive_autonomous_operations() -> None:
    from ois.infrastructure.source_gateway.outbox import OutboxEvent, SQLiteOutboxStore

    outbox = SQLiteOutboxStore()
    outbox.append(
        OutboxEvent(
            event_id="evt-outbox",
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            event_type="source.updated",
            aggregate_id="record-1",
            payload={"risk_level": "low", "source_id": "github"},
            created_at=datetime.now(UTC),
        )
    )

    calls: list[str] = []
    operations = AutonomousOperations(outbox=outbox, policy=allow_policy())
    operations.register_workflow(workflow(lambda evt: calls.append(evt.event_id)))

    receipts = operations.drain_outbox()

    assert len(receipts) == 1
    assert calls == ["evt-outbox"]
    assert outbox.pending() == ()
