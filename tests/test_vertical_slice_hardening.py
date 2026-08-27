import pytest

from ois.capabilities.tiktok_growth import TikTokContentAgent
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.policy import AuthorizationDenied, DefaultPolicyEngine
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus, InvocationStatus, RiskLevel, SideEffectLevel
from ois.workflows.tiktok_content_vertical_slice import execute_tiktok_vertical_slice


class FailingCapability:
    contract = AgentContract(
        capability_id="test.failing.capability",
        version="1.0.0",
        description="Synthetic failure capability",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        permissions=(),
        allowed_domains=(),
        timeout_seconds=1.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        required_tools=(),
        model_requirements={"external_model": False},
        max_iterations=1,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        raise RuntimeError("synthetic tool failure")


class RestrictedCapability:
    contract = AgentContract(
        capability_id="test.restricted.capability",
        version="1.0.0",
        description="Synthetic policy-denied capability",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        permissions=("restricted.execute",),
        allowed_domains=(),
        timeout_seconds=1.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
        required_tools=(),
        model_requirements={"external_model": False},
        max_iterations=1,
    )
    invoked = False

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.invoked = True
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"unexpected": True},
        )


def _context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="test-tenant",
            workflow_id="test.vertical",
            workflow_version="1.0.0",
        ),
        objective="vertical slice hardening",
    )


def _runtime(capability, *, policy=None):
    registry = CapabilityRegistry()
    registry.register(capability)
    checkpoint = InMemoryCheckpointStore()
    evidence = EvidenceLedger()
    return (
        ExecutionRuntime(
            registry,
            checkpoint,
            evidence,
            policy=policy,
        ),
        checkpoint,
        evidence,
    )


def test_vertical_slice_contract_is_canonical() -> None:
    result = execute_tiktok_vertical_slice(
        {
            "topic": "AI agents",
            "audience": "creators",
            "objective": "education",
            "tone": "clear",
        }
    )
    assert result.invocation.status == InvocationStatus.SUCCEEDED
    assert result.context.status == ExecutionStatus.COMPLETED
    assert result.plan.is_complete()
    assert result.context.validation_results[-1]["valid"] is True
    assert result.context.working_memory
    event_types = {event.event_type for event in result.evidence}
    assert {
        "execution.received",
        "execution.input_validated",
        "execution.authorized",
        "capability.started",
        "capability.completed",
        "execution.checkpointed",
        "execution.idempotency_recorded",
        "execution.completed",
    }.issubset(event_types)


def test_idempotency_returns_cached_result_for_same_invocation() -> None:
    runtime, checkpoint, evidence = _runtime(TikTokContentAgent())
    context = _context()
    first = runtime.execute(
        context,
        "tiktok.content.plan",
        "1.0.0",
        {"topic": "AI agents"},
        invocation_id="stable",
    )
    second = runtime.execute(
        context,
        "tiktok.content.plan",
        "1.0.0",
        {"topic": "AI agents"},
        invocation_id="stable",
    )
    assert first is second
    assert first.status == InvocationStatus.SUCCEEDED
    assert checkpoint.exists(context.identity.execution_id)
    assert "execution.idempotency_hit" in [
        event.event_type for event in evidence.list(context.identity.execution_id)
    ]


def test_failure_records_recovery_evidence_and_checkpoint() -> None:
    runtime, checkpoint, evidence = _runtime(FailingCapability())
    context = _context()
    result = runtime.execute(
        context,
        "test.failing.capability",
        "1.0.0",
        {},
        invocation_id="failure",
    )
    assert result.status == InvocationStatus.FAILED
    assert result.error["failure_class"] == "tool"
    assert result.error["recovery_action"] == "fallback"
    assert context.last_failure.value == "tool"
    assert checkpoint.exists(context.identity.execution_id)
    assert "execution.failure" in [
        event.event_type for event in evidence.list(context.identity.execution_id)
    ]


def test_policy_denial_blocks_execution_before_capability() -> None:
    capability = RestrictedCapability()
    runtime, checkpoint, evidence = _runtime(
        capability,
        policy=DefaultPolicyEngine(),
    )
    context = _context()
    with pytest.raises(AuthorizationDenied):
        runtime.execute(
            context,
            "test.restricted.capability",
            "1.0.0",
            {},
            invocation_id="denied",
        )
    assert capability.invoked is False
    assert checkpoint.exists(context.identity.execution_id) is False
    event_types = [event.event_type for event in evidence.list(context.identity.execution_id)]
    assert "execution.input_validated" in event_types
    assert "execution.authorized" not in event_types
    assert "capability.started" not in event_types
