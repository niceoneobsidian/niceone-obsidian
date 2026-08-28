import pytest
from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    CyclicPlanError,
    DuplicateTaskError,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    PlanBuilder,
    PlanExecutionError,
    PlanOrchestrator,
    TaskStatus,
    UnknownDependencyError,
)
from ois.kernel.evidence import EvidenceLedger


class EchoCapability:
    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.echo",
            version="1.0.0",
            description="Planning test capability",
            input_schema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"},
                },
            },
        )

    def invoke(self, request: InvocationRequest):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"message": request.input["message"]},
        )


class FailingCapability:
    @property
    def contract(self):
        return CapabilityContract(
            capability_id="test.fail",
            version="1.0.0",
            description="Always fails",
        )

    def invoke(self, request: InvocationRequest):
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.FAILED,
            error={
                "type": "TestFailure",
                "message": "Intentional planning test failure",
            },
        )


def make_runtime():
    registry = CapabilityRegistry()
    registry.register(EchoCapability())
    registry.register(FailingCapability())

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )


def make_context(objective):
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective=objective,
    )


# =========================
# PLAN STRUCTURE VALIDATION
# =========================


def test_duplicate_task_id_is_rejected():
    with pytest.raises(DuplicateTaskError):
        (
            PlanBuilder("duplicate test")
            .task(
                task_id="step-1",
                capability_id="test.echo",
                capability_version="1.0.0",
            )
            .task(
                task_id="step-1",
                capability_id="test.echo",
                capability_version="1.0.0",
            )
        )


def test_unknown_dependency_is_rejected():
    with pytest.raises(UnknownDependencyError):
        (
            PlanBuilder("dependency test")
            .task(
                task_id="step-1",
                capability_id="test.echo",
                capability_version="1.0.0",
                dependencies=("missing",),
            )
            .build()
        )


def test_cyclic_plan_is_rejected():
    with pytest.raises(CyclicPlanError):
        (
            PlanBuilder("cycle test")
            .task(
                task_id="step-1",
                capability_id="test.echo",
                capability_version="1.0.0",
                dependencies=("step-2",),
            )
            .task(
                task_id="step-2",
                capability_id="test.echo",
                capability_version="1.0.0",
                dependencies=("step-1",),
            )
            .build()
        )


# =========================
# READY-TASK SEMANTICS
# =========================


def test_ready_tasks_semantics():
    plan = (
        PlanBuilder("ready task test")
        .task(
            task_id="step-1",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "one"},
        )
        .task(
            task_id="step-2",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "two"},
        )
        .task(
            task_id="step-3",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "three"},
            dependencies=("step-1",),
        )
        .build()
    )

    ready = plan.ready_tasks()

    assert {task.task_id for task in ready} == {
        "step-1",
        "step-2",
    }

    assert plan.tasks["step-1"].status == TaskStatus.READY
    assert plan.tasks["step-2"].status == TaskStatus.READY
    assert plan.tasks["step-3"].status == TaskStatus.PENDING

    # Once the dependency succeeds, the dependent task becomes ready.
    plan.tasks["step-1"].status = TaskStatus.SUCCEEDED

    ready = plan.ready_tasks()

    assert {task.task_id for task in ready} == {"step-3"}
    assert plan.tasks["step-3"].status == TaskStatus.READY


# =========================
# SUCCESSFUL ORCHESTRATION
# =========================


def test_successful_orchestration_completes_plan():
    runtime = make_runtime()
    orchestrator = PlanOrchestrator(runtime)

    success_plan = (
        PlanBuilder("successful orchestration")
        .task(
            task_id="step-1",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "first"},
        )
        .task(
            task_id="step-2",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "second"},
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context(success_plan.objective)

    result = orchestrator.execute(success_plan, context)

    assert result.is_complete()
    assert result.tasks["step-1"].status == TaskStatus.SUCCEEDED
    assert result.tasks["step-2"].status == TaskStatus.SUCCEEDED
    assert context.status.value == "completed"


# =========================
# FAILED ORCHESTRATION
# =========================


def test_failed_orchestration_halts_plan_and_blocks_continuation():
    runtime = make_runtime()
    orchestrator = PlanOrchestrator(runtime)

    failure_plan = (
        PlanBuilder("failed orchestration")
        .task(
            task_id="step-1",
            capability_id="test.fail",
            capability_version="1.0.0",
        )
        .task(
            task_id="step-2",
            capability_id="test.echo",
            capability_version="1.0.0",
            input_data={"message": "should not execute"},
            dependencies=("step-1",),
        )
        .build()
    )

    context = make_context(failure_plan.objective)

    result_plan = orchestrator.execute(failure_plan, context)

    assert result_plan.tasks["step-1"].status == TaskStatus.FAILED
    assert result_plan.tasks["step-1"].error is not None
    assert result_plan.tasks["step-2"].status == TaskStatus.PENDING
    assert result_plan.is_complete() is False
    assert result_plan.has_failed() is True

    with pytest.raises(PlanExecutionError):
        orchestrator.execute(result_plan, context)

    # A failed plan must not be silently completed.
    with pytest.raises(PlanExecutionError):
        orchestrator.execute(failure_plan, context)
