from __future__ import annotations

from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.idempotency import InMemoryIdempotencyStore
from ois.kernel.policy import DefaultPolicyEngine
from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import FailureClass, InvocationStatus
from ois.registries import CapabilityRegistry


def test_spine_passes_explicit_idempotency_and_recovery_policies_to_runtime() -> None:
    idempotency = InMemoryIdempotencyStore()
    recovery = RecoveryPolicy(max_retries=1, max_recovery_attempts=1)

    spine = OISSpine(
        CapabilityRegistry(),
        idempotency=idempotency,
        recovery=recovery,
    )

    assert spine.runtime.idempotency is idempotency
    assert spine.runtime.recovery is recovery


class ProtectedImportCapability:
    contract = CapabilityContract(
        capability_id="ocif.import.consume",
        version="1.0.0",
        description="Test-only protected import capability.",
        permissions=("ocif.evidence.import",),
    )

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.calls += 1
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"imported": True},
        )


def test_missing_permission_denies_execution_before_capability_runs() -> None:
    registry = CapabilityRegistry()
    capability = ProtectedImportCapability()
    registry.register(capability)
    spine = OISSpine(registry, policy=DefaultPolicyEngine(allowed_permissions=()))

    result = spine.submit(
        SpineRequest(
            objective="Import evidence only when authorized",
            capability_id="ocif.import.consume",
            capability_version="1.0.0",
            tenant_id="tenant-test",
            input={"capture_id": "capture-test"},
        ),
        invocation_id="ocif-import-invocation-test",
    )

    assert result.status == "denied"
    assert capability.calls == 0
    event_types = {str(event["event_type"]) for event in result.evidence}
    assert "execution.authorization_denied" in event_types
    assert "spine.authorization.denied" in event_types


def test_recovery_policy_caps_transient_retry_decisions() -> None:
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-test"),
        objective="Test bounded recovery",
    )
    policy = RecoveryPolicy(max_retries=1, max_recovery_attempts=1)

    first = policy.apply(context, FailureClass.TRANSIENT)
    second = policy.classify(FailureClass.TRANSIENT, context)

    assert first.retry_allowed is True
    assert context.retry_count == 1
    assert second.retry_allowed is False
    assert second.terminal is True
