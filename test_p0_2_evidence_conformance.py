from __future__ import annotations

from pathlib import Path

import pytest

from ois.kernel import (
    AuthorizationDenied,
    CapabilityContract,
    CapabilityNotFoundError,
    CapabilityRegistry,
    DefaultPolicyEngine,
    ExecutionContext,
    ExecutionError,
    ExecutionIdentity,
    ExecutionRuntime,
    ExecutionStatus,
    FailureClass,
    InputValidationError,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
    SQLiteCheckpointStore,
    SQLiteEvidenceLedger,
    SQLiteIdempotencyStore,
)


class ValidCapability:
    def __init__(
        self,
        capability_id: str,
        *,
        output_valid: bool = True,
        counter: list[int] | None = None,
        permissions: tuple[str, ...] = (),
    ):
        self.capability_id = capability_id
        self.output_valid = output_valid
        self.counter = counter
        self.permissions = permissions

    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id=self.capability_id,
            version="1.0.0",
            description="P0.2 conformance capability.",
            input_schema={
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            },
            risk_level=RiskLevel.LOW,
            permissions=self.permissions,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        if self.counter is not None:
            self.counter[0] += 1
        output = {"value": request.input["value"]}
        if not self.output_valid:
            output = {"value": 42}
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
        )


class ConsequentialCapability(ValidCapability):
    @property
    def contract(self) -> CapabilityContract:
        base = super().contract
        return CapabilityContract(
            capability_id=base.capability_id,
            version=base.version,
            description=base.description,
            input_schema=base.input_schema,
            output_schema=base.output_schema,
            risk_level=base.risk_level,
            permissions=base.permissions,
            side_effects=SideEffectLevel.REVERSIBLE,
        )


def make_runtime(tmp_path: Path, capabilities, *, policy=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    registry = CapabilityRegistry()
    for capability in capabilities:
        registry.register(capability)
    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=SQLiteCheckpointStore(str(tmp_path / "checkpoints.db")),
        evidence=SQLiteEvidenceLedger(str(tmp_path / "evidence.db")),
        idempotency=SQLiteIdempotencyStore(str(tmp_path / "idempotency.db")),
        policy=policy or DefaultPolicyEngine(),
    )


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="p0.2"),
        objective="P0.2 evidence conformance",
    )


def event_types(runtime: ExecutionRuntime, execution_id):
    return [event.event_type for event in runtime.evidence.list(execution_id)]


def test_validation_gate_blocks_completion_records_failure_and_replans(tmp_path: Path):
    runtime = make_runtime(
        tmp_path,
        [ValidCapability("test.invalid", output_valid=False)],
    )
    context = make_context()

    result = runtime.execute(
        context,
        "test.invalid",
        "1.0.0",
        {"value": "bad-output"},
        idempotency_key="validation-1",
    )

    assert result.status == InvocationStatus.FAILED
    assert result.error["failure_class"] == FailureClass.PLAN.value
    assert result.error["recovery_action"] == "replan"
    assert context.status == ExecutionStatus.REPLANNING
    assert context.validation_results[-1]["valid"] is False

    with pytest.raises(ExecutionError, match="failed validation|recovery state"):
        runtime.complete(context)

    events = event_types(runtime, context.identity.execution_id)
    assert "execution.validation_failed" in events
    assert "execution.recovery_decision" in events
    assert "execution.completion_blocked" in events
    assert "execution.completed" not in events


def test_checkpoint_interruption_resume_does_not_repeat_completed_work(tmp_path: Path):
    counter = [0]
    capability = ValidCapability("test.step", counter=counter)
    runtime = make_runtime(tmp_path, [capability])
    context = make_context()

    first = runtime.execute(
        context,
        "test.step",
        "1.0.0",
        {"value": "first"},
        idempotency_key="step-1",
    )
    assert first.status == InvocationStatus.SUCCEEDED
    assert counter[0] == 1

    checkpointed = runtime.checkpoint_store.load(context.identity.execution_id)
    assert checkpointed.status == ExecutionStatus.ROUTED

    resumed = runtime.checkpoint_store.load(context.identity.execution_id)
    second = runtime.execute(
        resumed,
        "test.step",
        "1.0.0",
        {"value": "second"},
        idempotency_key="step-2",
    )
    assert second.status == InvocationStatus.SUCCEEDED
    assert counter[0] == 2

    replayed_first = runtime.execute(
        resumed,
        "test.step",
        "1.0.0",
        {"value": "first"},
        idempotency_key="step-1",
    )
    assert replayed_first.invocation_id == first.invocation_id
    assert replayed_first.output == first.output
    assert counter[0] == 2

    events = event_types(runtime, context.identity.execution_id)
    assert "execution.checkpointed" in events
    assert "execution.idempotency_hit" in events


def test_true_idempotency_one_effect_same_governed_result_across_runtime_restart(
    tmp_path: Path,
):
    counter = [0]
    capability = ConsequentialCapability("test.effect", counter=counter)

    runtime_one = make_runtime(tmp_path, [capability])
    context_one = make_context()
    first = runtime_one.execute(
        context_one,
        "test.effect",
        "1.0.0",
        {"value": "charge"},
        idempotency_key="effect-42",
    )
    assert first.status == InvocationStatus.SUCCEEDED
    assert counter[0] == 1

    runtime_two = make_runtime(tmp_path, [capability])
    context_two = runtime_two.checkpoint_store.load(context_one.identity.execution_id)
    second = runtime_two.execute(
        context_two,
        "test.effect",
        "1.0.0",
        {"value": "charge"},
        idempotency_key="effect-42",
    )

    assert second.invocation_id == first.invocation_id
    assert second.output == first.output
    assert counter[0] == 1
    hit = next(
        event
        for event in runtime_two.evidence.list(context_two.identity.execution_id)
        if event.event_type == "execution.idempotency_hit"
    )
    assert hit.data["idempotency_key"] == "effect-42"
    assert hit.data["effect_invocation_id"] == first.invocation_id


def test_negative_controls_reject_without_execution_and_causal_evidence_is_ordered(
    tmp_path: Path,
):
    counter = [0]
    capability = ValidCapability("test.secure", counter=counter)
    runtime = make_runtime(tmp_path, [capability])
    context = make_context()

    with pytest.raises(CapabilityNotFoundError):
        runtime.execute(
            context,
            "test.unknown",
            "1.0.0",
            {"value": "x"},
            idempotency_key="unknown-1",
        )
    assert counter[0] == 0

    with pytest.raises(InputValidationError):
        runtime.execute(
            context,
            "test.secure",
            "1.0.0",
            {"value": 123},
            idempotency_key="malformed-1",
        )
    assert counter[0] == 0

    restricted = ValidCapability(
        "test.restricted",
        counter=counter,
        permissions=("restricted.execute",),
    )
    denied_runtime = make_runtime(tmp_path / "denied", [restricted])
    denied_context = make_context()
    with pytest.raises(AuthorizationDenied):
        denied_runtime.execute(
            denied_context,
            "test.restricted",
            "1.0.0",
            {"value": "blocked"},
            idempotency_key="unauthorized-1",
        )
    assert counter[0] == 0

    events = event_types(runtime, context.identity.execution_id)
    assert events.index("execution.received") < events.index("execution.input_validated")
    assert "execution.authorized" not in events
    assert "capability.started" not in events

    denied_events = event_types(denied_runtime, denied_context.identity.execution_id)
    assert "execution.received" in denied_events
    assert "execution.input_validated" in denied_events
    assert "execution.authorized" not in denied_events
    assert "capability.started" not in denied_events
