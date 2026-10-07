from __future__ import annotations

from ois.autonomy.durable import DurableRunStatus, DurableWorkflowRun
from ois.autonomy.engine import DurableAutonomousExecutionEngine
from ois.autonomy.events import EventEnvelope
from ois.autonomy.policy import AutomationPolicy, PolicyRule
from ois.autonomy.workflows import SourceWorkflow, WorkflowTrigger
from ois.kernel.types import RiskLevel


class Runs:
    def __init__(self):
        self.run = None

    def create(self, run):
        self.run = run
        return run

    def claim_idempotency(self, run):
        return True

    def get_by_event(self, **_kwargs):
        return self.run


class Leases:
    def claim(self, run_id, worker_id):
        return type("Lease", (), {"execution_id": run_id, "worker_id": worker_id, "epoch": 1})()

    def release(self, lease):
        return None

    def assert_current(self, lease):
        return None


class Approvals:
    def get_by_event(self, event_id):
        return None

    def create(self, request, *, run_id=None):
        return request

    def get(self, approval_id):
        return None


class Effects:
    pass


class Fenced:
    def __init__(self, repo, leases, lease):
        self.run = repo.run

    def transition(self, run_id, *, status, attempt=None, checkpoint=None, result=None, error=None):
        self.run = DurableWorkflowRun(
            **{
                **self.run.__dict__,
                "status": status,
                "attempt": attempt if attempt is not None else self.run.attempt,
                "checkpoint": checkpoint if checkpoint is not None else self.run.checkpoint,
                "result": result,
                "error": error,
            }
        )
        return self.run


def test_unified_engine_completes_through_kernel_owned_callback(monkeypatch) -> None:
    import ois.autonomy.engine as engine_module

    monkeypatch.setattr(engine_module, "FencedPostgresWorkflowRunRepository", Fenced)
    runs = Runs()
    engine = DurableAutonomousExecutionEngine(
        runs=runs,
        leases=Leases(),
        approvals=Approvals(),
        side_effects=Effects(),
        policy=AutomationPolicy(
            (PolicyRule(rule_id="allow", event_type="source.event", maximum_risk=RiskLevel.HIGH),)
        ),
    )
    workflow = SourceWorkflow(
        workflow_id="wf",
        version="1",
        tenant_id="t",
        workspace_id="w",
        trigger=WorkflowTrigger(event_type="source.event"),
        action=lambda event: {"unused": True},
    )
    event = EventEnvelope(
        event_id="event-1",
        tenant_id="t",
        workspace_id="w",
        event_type="source.event",
        aggregate_id="aggregate-1",
    )
    receipt = engine.start(
        workflow=workflow,
        event=event,
        worker_id="worker-a",
        execute=lambda wf, evt: {"ok": True},
    )
    assert receipt.run.status == DurableRunStatus.COMPLETED
    assert receipt.run.result == {"ok": True}
