"""
Phase 6 — Orchestrator recovery boundary contract tests.

Covers: failed task, blocked DAG, no false completion.

NOTE ON A KNOWN GAP (documented, not silently patched over):
PlanOrchestrator.execute() returns immediately (inside the `for task in
ready:` loop) on the FIRST task failure within a ready batch. This means
independent, unrelated branches that are ready in the same batch as a
failing task do NOT get a chance to run, even though nothing depends on
the failed branch. The hardening plan calls for "independent branches
continue" on partial failure; the current implementation halts the
entire plan on first failure instead. test_sibling_branch_does_not_run_
after_earlier_branch_fails_in_same_batch documents this as current
behavior so the gap is visible, not hidden.

NOTE ON REPLAN BOUNDARY: PlanOrchestrator has no replan logic at all --
there is no method or branch in execute() that re-plans around a failed
subgraph. This is a genuine missing feature, not merely an untested one.
No test is written to simulate it, since doing so would misrepresent
capability that does not exist.
"""

import pytest

from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    PlanBuilder,
    PlanOrchestrator,
    RiskLevel,
    SideEffectLevel,
    TaskStatus,
)
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.orchestrator import PlanExecutionError
from ois.kernel.types import ExecutionStatus


class RecordingCapability:
    def __init__(self, capability_id, should_fail=False):  # type: ignore
        self.capability_id = capability_id
        self.should_fail = should_fail
        self.invocations = 0

    @property
    def contract(self):  # type: ignore
        return CapabilityContract(
            capability_id=self.capability_id,
            version="1.0.0",
            description="Orchestrator boundary test capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest):  # type: ignore
        self.invocations += 1

        if self.should_fail:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=request.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": "TestFailure",
                    "message": "Intentional test failure",
                },
            )

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"executed": True},
        )


def make_runtime(*capabilities):  # type: ignore
    registry = CapabilityRegistry()

    for capability in capabilities:
        registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )


def make_context():  # type: ignore
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="Orchestrator recovery boundary test",
    )


def test_single_failed_task_halts_plan_without_completing():  # type: ignore
    upstream = RecordingCapability("test.upstream")
    downstream = RecordingCapability("test.downstream", should_fail=True)

    runtime = make_runtime(upstream, downstream)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(objective="Single failure boundary")
        .task(
            task_id="step-1",
            capability_id="test.upstream",
            capability_version="1.0.0",
        )
        .task(
            task_id="step-2",
            capability_id="test.downstream",
            capability_version="1.0.0",
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context()

    result = orchestrator.execute(plan, context)

    assert result.is_complete() is False
    assert result.has_failed() is True
    assert result.tasks["step-1"].status == TaskStatus.SUCCEEDED
    assert result.tasks["step-2"].status == TaskStatus.FAILED
    assert upstream.invocations == 1
    assert downstream.invocations == 1


def test_sibling_branch_runs_independently_after_earlier_branch_fails_in_same_batch():  # type: ignore
    """
    Branch isolation is implemented: branch-fail and branch-ok have NO
    dependency relationship and are both ready in the same batch.
    PlanOrchestrator.execute() now continues processing independent
    siblings in the batch instead of returning on the first failure, so
    branch-ok still runs and succeeds even though branch-fail failed.
    """
    failing = RecordingCapability("test.branch-fail", should_fail=True)
    independent = RecordingCapability("test.branch-ok")

    runtime = make_runtime(failing, independent)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(objective="Sibling branch isolation check")
        .task(
            task_id="branch-fail",
            capability_id="test.branch-fail",
            capability_version="1.0.0",
        )
        .task(
            task_id="branch-ok",
            capability_id="test.branch-ok",
            capability_version="1.0.0",
        )
        .build()
    )

    context = make_context()

    result = orchestrator.execute(plan, context)

    assert result.tasks["branch-fail"].status == TaskStatus.FAILED
    assert failing.invocations == 1

    # The independent sibling has no dependency on the failed task, so it
    # still runs to completion within the same batch.
    assert independent.invocations == 1
    assert result.tasks["branch-ok"].status == TaskStatus.SUCCEEDED


def test_blocked_plan_raises_when_no_task_is_ready_and_none_failed():  # type: ignore
    """
    Force a blocked state deterministically: task-stuck is manually set
    to RUNNING before execute() is called, so it is never picked up by
    ready_tasks() (which only selects PENDING tasks) and never
    transitions further. task-blocked depends on task-stuck, so it can
    never become ready either. No task is FAILED, so the orchestrator
    must hit the "may be blocked" branch rather than the "failed" branch.
    """
    stuck_capability = RecordingCapability("test.stuck")
    blocked_capability = RecordingCapability("test.blocked")

    runtime = make_runtime(stuck_capability, blocked_capability)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(objective="Blocked DAG detection")
        .task(
            task_id="task-stuck",
            capability_id="test.stuck",
            capability_version="1.0.0",
        )
        .task(
            task_id="task-blocked",
            capability_id="test.blocked",
            capability_version="1.0.0",
            dependencies=("task-stuck",),
        )
        .build()
    )

    plan.tasks["task-stuck"].status = TaskStatus.RUNNING

    context = make_context()

    with pytest.raises(PlanExecutionError, match="blocked"):
        orchestrator.execute(plan, context)

    assert stuck_capability.invocations == 0
    assert blocked_capability.invocations == 0


def test_failed_plan_never_marks_execution_context_completed():  # type: ignore
    ok = RecordingCapability("test.ok")
    fails = RecordingCapability("test.fails", should_fail=True)

    runtime = make_runtime(ok, fails)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(objective="No false completion on failure")
        .task(
            task_id="step-1",
            capability_id="test.ok",
            capability_version="1.0.0",
        )
        .task(
            task_id="step-2",
            capability_id="test.fails",
            capability_version="1.0.0",
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context()

    orchestrator.execute(plan, context)

    assert context.status != ExecutionStatus.COMPLETED


def test_fully_successful_plan_marks_execution_context_completed():  # type: ignore
    first = RecordingCapability("test.first")
    second = RecordingCapability("test.second")

    runtime = make_runtime(first, second)
    orchestrator = PlanOrchestrator(runtime)

    plan = (
        PlanBuilder(objective="True completion on full success")
        .task(
            task_id="step-1",
            capability_id="test.first",
            capability_version="1.0.0",
        )
        .task(
            task_id="step-2",
            capability_id="test.second",
            capability_version="1.0.0",
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context()

    result = orchestrator.execute(plan, context)

    assert result.is_complete() is True
    assert result.has_failed() is False
    assert context.status == ExecutionStatus.COMPLETED
