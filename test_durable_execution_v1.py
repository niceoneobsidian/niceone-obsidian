import sqlite3
from pathlib import Path

import pytest

from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionPlan,
    ExecutionRuntime,
    FailureClass,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    PlanOrchestrator,
    RecoveryPolicy,
    RiskLevel,
    SideEffectLevel,
    SQLiteCheckpointStore,
    SQLiteEvidenceLedger,
    SQLiteIdempotencyStore,
    TaskNode,
    TaskStatus,
)


class CountingCapability:
    def __init__(self, capability_id: str = "test.durable") -> None:
        self.invocations = 0
        self._contract = CapabilityContract(
            capability_id=capability_id,
            version="1.0.0",
            description="Durable execution test capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.invocations += 1
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"invocations": self.invocations},
        )


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="durable-test",
            workflow_id="durable-v1",
            workflow_version="1.0.0",
        ),
        objective="prove durable execution",
    )


def make_runtime(capability: CountingCapability, root: Path) -> ExecutionRuntime:
    registry = CapabilityRegistry()
    registry.register(capability)
    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=SQLiteCheckpointStore(str(root / "state.db")),
        evidence=SQLiteEvidenceLedger(str(root / "evidence.db")),
        idempotency=SQLiteIdempotencyStore(str(root / "state.db")),
    )


def test_checkpoint_and_idempotency_survive_runtime_recreation(tmp_path: Path) -> None:
    capability = CountingCapability()
    runtime = make_runtime(capability, tmp_path)
    context = make_context()

    first = runtime.execute(
        context,
        "test.durable",
        "1.0.0",
        {"value": 1},
        invocation_id="execution-1:task-1",
    )
    execution_id = context.identity.execution_id
    runtime.checkpoint_store.save(context)

    restored_runtime = make_runtime(capability, tmp_path)
    restored = restored_runtime.checkpoint_store.load(execution_id)
    second = restored_runtime.execute(
        restored,
        "test.durable",
        "1.0.0",
        {"value": 1},
        invocation_id="execution-1:task-1",
    )

    assert first.status == InvocationStatus.SUCCEEDED
    assert second.status == InvocationStatus.SUCCEEDED
    assert second.output == first.output
    assert capability.invocations == 1
    assert restored.identity.execution_id == execution_id


def test_plan_resume_skips_succeeded_tasks_and_replays_only_pending(tmp_path: Path) -> None:
    first_capability = CountingCapability("test.first")
    second_capability = CountingCapability("test.second")
    checkpoint = SQLiteCheckpointStore(str(tmp_path / "state.db"))
    idempotency = SQLiteIdempotencyStore(str(tmp_path / "state.db"))
    evidence = SQLiteEvidenceLedger(str(tmp_path / "evidence.db"))
    registry = CapabilityRegistry()
    registry.register(first_capability)
    registry.register(second_capability)
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint,
        evidence=evidence,
        idempotency=idempotency,
    )
    context = make_context()
    plan = ExecutionPlan(objective=context.objective)
    plan.add_task(TaskNode("first", "test.first", "1.0.0"))
    plan.add_task(TaskNode("second", "test.second", "1.0.0", dependencies=("first",)))

    first_result = runtime.execute(
        context,
        "test.first",
        "1.0.0",
        {},
        invocation_id=f"{context.identity.execution_id}:first",
    )
    plan.tasks["first"].status = TaskStatus.SUCCEEDED
    plan.tasks["first"].output = first_result.output
    plan.tasks["second"].status = TaskStatus.RUNNING
    context.plan = plan.to_dict()
    checkpoint.save(context)

    resumed_plan, resumed_context = PlanOrchestrator(runtime).resume(context.identity.execution_id)

    assert resumed_plan.is_complete()
    assert resumed_context.status == resumed_context.status.COMPLETED
    assert first_capability.invocations == 1
    assert second_capability.invocations == 1


def test_corrupt_checkpoint_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    checkpoint = SQLiteCheckpointStore(str(database))
    context = make_context()
    checkpoint.save(context)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE execution_checkpoints SET state_hash = 'corrupt' WHERE execution_id = ?",
            (str(context.identity.execution_id),),
        )
        connection.commit()

    with pytest.raises(Exception, match="integrity hash mismatch"):
        checkpoint.load(context.identity.execution_id)


def test_failure_is_not_cached_as_success(tmp_path: Path) -> None:
    class FailingCapability(CountingCapability):
        def invoke(self, request: InvocationRequest) -> InvocationResult:
            self.invocations += 1
            raise RuntimeError("temporary tool failure")

    capability = FailingCapability("test.failure")
    runtime = make_runtime(capability, tmp_path)
    context = make_context()

    first = runtime.execute(context, "test.failure", "1.0.0", {}, invocation_id="failure-1")
    second = runtime.execute(context, "test.failure", "1.0.0", {}, invocation_id="failure-1")

    assert first.status == InvocationStatus.FAILED
    assert second.status == InvocationStatus.FAILED
    assert capability.invocations == 2


def test_recovery_policy_is_bounded() -> None:
    context = make_context()
    policy = RecoveryPolicy(max_retries=1)

    first = policy.apply(context, FailureClass.TRANSIENT)
    assert first.action == "retry"
    assert context.retry_count == 1

    second = policy.apply(context, FailureClass.TRANSIENT)
    assert second.action == "escalate"
    assert second.terminal is True
