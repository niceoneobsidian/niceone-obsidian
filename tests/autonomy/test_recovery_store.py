from __future__ import annotations

from uuid import UUID

from ois.autonomy.durable import DurableRunStatus, DurableWorkflowRun
from ois.autonomy.recovery_store import WorkflowRecoverySweeper


def test_resume_returns_latest_durable_checkpoint() -> None:
    run = DurableWorkflowRun(
        run_id=UUID("00000000-0000-0000-0000-000000000003"),
        tenant_id="tenant",
        workspace_id="workspace",
        workflow_id="workflow",
        workflow_version="1",
        event_id="event",
        status=DurableRunStatus.RECOVERING,
        checkpoint={"step": 4, "cursor": "abc"},
        idempotency_key="tenant:workspace:workflow:1:event",
    )

    class Repository:
        def get(self, run_id):
            return run

    sweeper = WorkflowRecoverySweeper.__new__(WorkflowRecoverySweeper)
    sweeper._repository = Repository()
    assert sweeper.resume(run.run_id) == {"step": 4, "cursor": "abc"}
