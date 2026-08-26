from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4

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
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.checkpoint import CheckpointConflict, PostgresCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.idempotency import PostgresIdempotencyStore

POSTGRES_DSN = os.getenv("OIS_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not POSTGRES_DSN, reason="OIS_POSTGRES_DSN is required")


@pytest.fixture
def database() -> str:
    assert POSTGRES_DSN is not None
    import psycopg

    schema = Path("ois/kernel/migrations/001_durable_execution.sql").read_text()
    with psycopg.connect(POSTGRES_DSN) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema)
    return POSTGRES_DSN


class CountingCapability:
    def __init__(self) -> None:
        self.invocations = 0
        self.lock = Lock()

    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="test.de02",
            version="1.0.0",
            description="DE-02 concurrency capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        with self.lock:
            self.invocations += 1
            count = self.invocations
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"invocations": count},
        )


def make_context(execution_id=None) -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=execution_id or uuid4(),
            tenant_id="de02-test",
        ),
        objective="DE-02 durable execution test",
    )


def test_checkpoint_survives_store_restart(database: str) -> None:
    execution_id = uuid4()
    first = PostgresCheckpointStore(database)
    context = make_context(execution_id)
    context.current_node = "before-crash"
    first.save(context)

    second = PostgresCheckpointStore(database)
    restored = second.load(execution_id)

    assert restored.identity.execution_id == execution_id
    assert restored.current_node == "before-crash"
    assert restored.checkpoint_version == 1


def test_checkpoint_rejects_stale_writer(database: str) -> None:
    execution_id = uuid4()
    store = PostgresCheckpointStore(database)
    original = make_context(execution_id)
    store.save(original)

    stale = store.load(execution_id)
    fresh = store.load(execution_id)
    fresh.current_node = "fresh"
    store.save(fresh)
    stale.current_node = "stale"

    with pytest.raises(CheckpointConflict):
        store.save(stale)


def test_concurrent_claim_has_single_winner(database: str) -> None:
    invocation_id = f"de02-{uuid4()}"

    def claim() -> bool:
        store = PostgresIdempotencyStore(database)
        return store.claim(invocation_id, lease_seconds=10).acquired

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: claim(), range(2)))

    assert sum(results) == 1


def test_runtime_concurrent_duplicate_executes_capability_once(database: str) -> None:
    capability = CountingCapability()
    registry = CapabilityRegistry()
    registry.register(capability)
    invocation_id = f"shared-{uuid4()}"

    def invoke() -> InvocationResult:
        runtime = ExecutionRuntime(
            registry=registry,
            checkpoint_store=PostgresCheckpointStore(database),
            evidence=EvidenceLedger(),
            idempotency=PostgresIdempotencyStore(database),
        )
        return runtime.execute(
            context=make_context(),
            capability_id="test.de02",
            version="1.0.0",
            input_data={"value": 1},
            invocation_id=invocation_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: invoke(), range(2)))

    assert capability.invocations == 1
    assert all(result.status == InvocationStatus.SUCCEEDED for result in results)
    assert results[0].output == results[1].output
