from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from ois.kernel import (
    CapabilityContract,
    CapabilityRegistry,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
)
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore


class CountingCapability:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="test.durable-echo",
            version="1.0.0",
            description="A side-effect-free persistence test capability.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("intentional persistence test failure")
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"message": request.input["message"], "call": self.calls},
        )


def stores(dsn: str) -> tuple[
    PostgresDurableExecutionStore, PostgresIdempotencyStore, PostgresEvidenceLedger
]:
    connect = lambda: psycopg.connect(dsn)
    checkpoints = PostgresDurableExecutionStore(connect)
    idempotency = PostgresIdempotencyStore(connect)
    evidence = PostgresEvidenceLedger(connect)
    checkpoints.initialize()
    idempotency.initialize()
    evidence.initialize()
    return checkpoints, idempotency, evidence


def test_kernel_postgres_stores_survive_runtime_recreation(
    migrated_postgres: str,
) -> None:
    checkpoint_store, idempotency_store, evidence = stores(migrated_postgres)
    registry = CapabilityRegistry()
    capability = CountingCapability()
    registry.register(capability)
    execution_id = uuid4()
    invocation_id = f"durable-replay-{uuid4()}"
    context = ExecutionContext(
        identity=ExecutionIdentity(execution_id=execution_id, tenant_id="default"),
        objective="Verify durable Kernel replay",
    )
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store,
        evidence=evidence,
        idempotency=idempotency_store,
    )
    first = runtime.execute(
        context,
        "test.durable-echo",
        "1.0.0",
        {"message": "original"},
        invocation_id=invocation_id,
    )
    assert first.status is InvocationStatus.SUCCEEDED
    assert capability.calls == 1
    first_events = evidence.list(execution_id)
    assert first_events

    checkpoint_store.close()
    idempotency_store.close()
    evidence.close()

    checkpoint_store_2, idempotency_store_2, evidence_2 = stores(migrated_postgres)
    restored_context = checkpoint_store_2.load(execution_id)
    assert restored_context.identity.execution_id == execution_id
    assert restored_context.working_memory[f"result:{invocation_id}"] == first.output
    restored_events = evidence_2.list(execution_id)
    assert [event.event_id for event in restored_events] == [
        event.event_id for event in first_events
    ]

    runtime_2 = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store_2,
        evidence=evidence_2,
        idempotency=idempotency_store_2,
    )
    replay = runtime_2.execute(
        restored_context,
        "test.durable-echo",
        "1.0.0",
        {"message": "must not replace original"},
        invocation_id=invocation_id,
    )
    assert replay.output == first.output
    assert replay.status is first.status
    assert capability.calls == 1
    assert any(
        event.event_type == "execution.idempotency_hit"
        for event in evidence_2.list(execution_id)
    )

    checkpoint_store_2.close()
    idempotency_store_2.close()
    evidence_2.close()


def test_kernel_postgres_idempotency_does_not_cache_failed_invocations(
    migrated_postgres: str,
) -> None:
    checkpoint_store, idempotency_store, evidence = stores(migrated_postgres)
    registry = CapabilityRegistry()
    capability = CountingCapability(fail=True)
    registry.register(capability)
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store,
        evidence=evidence,
        idempotency=idempotency_store,
    )
    invocation_id = f"failed-not-cached-{uuid4()}"

    first = runtime.execute(
        ExecutionContext(identity=ExecutionIdentity(), objective="failure retry"),
        "test.durable-echo",
        "1.0.0",
        {"message": "retry me"},
        invocation_id=invocation_id,
    )
    second = runtime.execute(
        ExecutionContext(identity=ExecutionIdentity(), objective="failure retry"),
        "test.durable-echo",
        "1.0.0",
        {"message": "retry me"},
        invocation_id=invocation_id,
    )

    assert first.status is InvocationStatus.FAILED
    assert second.status is InvocationStatus.FAILED
    assert capability.calls == 2
    assert idempotency_store.get(invocation_id) is None
    assert evidence.count() > 0
    checkpoint_store.close()
    idempotency_store.close()
    evidence.close()


def test_kernel_postgres_evidence_is_append_only(migrated_postgres: str) -> None:
    _, _, evidence = stores(migrated_postgres)
    execution_id = uuid4()
    event = evidence.record(execution_id, "test.persisted", {"safe": True})
    assert evidence.list(execution_id)[0].event_id == event.event_id

    with pytest.raises(psycopg.Error, match="append-only"):
        with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM ois_kernel_evidence_events WHERE event_id = %s",
                (event.event_id,),
            )
    evidence.close()
