from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionLease,
    ExecutionRuntime,
    InvocationResult,
    InvocationStatus,
    LeaseLost,
    LeaseUnavailable,
    PostgreSQLCheckpointStore,
    PostgreSQLExecutionCoordinator,
    PostgreSQLIdempotencyStore,
)

DSN = os.getenv("OIS_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="OIS_POSTGRES_DSN is not configured")


class EchoCapability:
    contract = CapabilityContract(
        capability_id="test.echo",
        version="1.0.0",
        description="PostgreSQL conformance capability",
        input_schema={"type": "object", "required": ["value"]},
        output_schema={"type": "object", "required": ["value"]},
    )

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, request):
        self.calls += 1
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"value": request.input["value"]},
        )


def context() -> ExecutionContext:
    return ExecutionContext(identity=ExecutionIdentity(tenant_id="conformance"), objective="postgres conformance")


def stores():
    assert DSN
    return PostgreSQLCheckpointStore(DSN), PostgreSQLIdempotencyStore(DSN), PostgreSQLExecutionCoordinator(DSN)


def test_checkpoint_survives_restart() -> None:
    checkpoint, _, _ = stores()
    original = context()
    checkpoint.save(original)
    restored = checkpoint.load(original.identity.execution_id)
    assert restored.identity.execution_id == original.identity.execution_id
    assert restored.objective == original.objective
    assert checkpoint.revision(original.identity.execution_id) >= 1


def test_concurrent_first_writer_wins() -> None:
    _, idempotency, _ = stores()
    invocation_id = f"conformance-{uuid4()}"
    results = [
        InvocationResult(invocation_id, "test.echo", InvocationStatus.SUCCEEDED, output={"winner": i})
        for i in range(8)
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        inserted = list(pool.map(lambda result: idempotency.put_if_absent(invocation_id, result), results))
    assert sum(inserted) == 1
    stored = idempotency.get(invocation_id)
    assert stored is not None
    assert stored.invocation_id == invocation_id


def test_only_one_live_worker_can_claim() -> None:
    _, _, coordinator = stores()
    execution_id = uuid4()
    first = coordinator.claim(execution_id, "conformance", "worker-a", ttl_seconds=30)
    with pytest.raises(LeaseUnavailable):
        coordinator.claim(execution_id, "conformance", "worker-b", ttl_seconds=30)
    coordinator.assert_current(first)


def test_expired_worker_is_fenced_after_takeover() -> None:
    _, _, coordinator = stores()
    execution_id = uuid4()
    stale = coordinator.claim(execution_id, "conformance", "worker-a", ttl_seconds=-1)
    current = coordinator.claim(execution_id, "conformance", "worker-b", ttl_seconds=30)
    assert current.lease_epoch > stale.lease_epoch
    with pytest.raises(LeaseLost):
        coordinator.assert_current(stale)
    coordinator.assert_current(current)


def test_runtime_honors_lease_and_rejects_stale_worker() -> None:
    checkpoint, idempotency, coordinator = stores()
    registry = CapabilityRegistry()
    capability = EchoCapability()
    registry.register(capability)
    runtime = ExecutionRuntime(
        registry,
        checkpoint,
        EvidenceLedger(),
        idempotency=idempotency,
        coordinator=coordinator,
    )
    execution = context()
    stale = coordinator.claim(execution.identity.execution_id, "conformance", "worker-a", ttl_seconds=-1)
    current = coordinator.claim(execution.identity.execution_id, "conformance", "worker-b", ttl_seconds=30)
    with pytest.raises(LeaseLost):
        runtime.execute(execution, "test.echo", "1.0.0", {"value": "stale"}, invocation_id="fenced-1", lease=stale)
    result = runtime.execute(
        execution, "test.echo", "1.0.0", {"value": "current"}, invocation_id="fenced-1", lease=current
    )
    assert result.status == InvocationStatus.SUCCEEDED
    assert capability.calls == 1


def test_full_durable_runtime_round_trip() -> None:
    checkpoint, idempotency, coordinator = stores()
    registry = CapabilityRegistry()
    capability = EchoCapability()
    registry.register(capability)
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry,
        checkpoint,
        evidence,
        idempotency=idempotency,
        coordinator=coordinator,
    )
    execution = context()
    lease = coordinator.claim(execution.identity.execution_id, "conformance", "worker-a")
    result = runtime.execute(
        execution,
        "test.echo",
        "1.0.0",
        {"value": "durable"},
        invocation_id=f"round-trip-{execution.identity.execution_id}",
        lease=lease,
    )
    assert result.status == InvocationStatus.SUCCEEDED
    restored = checkpoint.load(execution.identity.execution_id)
    assert restored.working_memory
    cached = runtime.execute(
        restored,
        "test.echo",
        "1.0.0",
        {"value": "durable"},
        invocation_id=result.invocation_id,
        lease=lease,
    )
    assert cached.output == result.output
    assert capability.calls == 1
