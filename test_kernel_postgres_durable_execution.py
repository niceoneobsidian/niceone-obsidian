import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from ois.kernel import ExecutionContext, ExecutionIdentity, InvocationResult, InvocationStatus
from ois.kernel.postgres import PostgreSQLCheckpointStore, PostgreSQLIdempotencyStore

POSTGRES_DSN = os.getenv("OIS_POSTGRES_DSN") or ""
pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN,
    reason="OIS_POSTGRES_DSN is required for PostgreSQL integration tests",
)


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="tenant-de-02", workflow_id="durable-test"),
        objective="PostgreSQL durable execution",
    )


def make_result(invocation_id: str) -> InvocationResult:
    return InvocationResult(
        invocation_id=invocation_id,
        capability_id="test.capability",
        status=InvocationStatus.SUCCEEDED,
        output={"value": 42},
        metadata={"source": "de-02"},
    )


def test_postgres_checkpoint_survives_store_recreation():
    execution_id = uuid4()
    first = PostgreSQLCheckpointStore(POSTGRES_DSN)
    context = make_context()
    context.identity = ExecutionIdentity(
        execution_id=execution_id,
        tenant_id=context.identity.tenant_id,
        workflow_id=context.identity.workflow_id,
    )
    context.working_memory["survives_restart"] = {"answer": 42}
    first.save(context)

    second = PostgreSQLCheckpointStore(POSTGRES_DSN)
    restored = second.load(execution_id)

    assert restored.identity.execution_id == execution_id
    assert restored.identity.tenant_id == "tenant-de-02"
    assert restored.working_memory["survives_restart"] == {"answer": 42}
    assert restored.status == context.status
    assert restored.created_at == context.created_at

    first.delete(execution_id)


def test_postgres_checkpoint_writes_are_atomic_under_concurrency():
    execution_id = uuid4()
    seed = make_context()
    seed.identity = ExecutionIdentity(execution_id=execution_id, tenant_id="tenant-de-02")
    PostgreSQLCheckpointStore(POSTGRES_DSN).save(seed)

    def write(value: int) -> None:
        context = make_context()
        context.identity = ExecutionIdentity(execution_id=execution_id, tenant_id="tenant-de-02")
        context.working_memory["writer"] = value
        PostgreSQLCheckpointStore(POSTGRES_DSN).save(context)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(8)))

    store = PostgreSQLCheckpointStore(POSTGRES_DSN)
    restored = store.load(execution_id)
    assert restored.working_memory["writer"] in range(8)
    assert store.revision(execution_id) == 9
    store.delete(execution_id)


def test_postgres_idempotency_survives_store_recreation():
    invocation_id = f"restart-{uuid4()}"
    first = PostgreSQLIdempotencyStore(POSTGRES_DSN)
    result = make_result(invocation_id)
    first.put(invocation_id, result)

    second = PostgreSQLIdempotencyStore(POSTGRES_DSN)
    restored = second.get(invocation_id)

    assert restored is not None
    assert restored.invocation_id == invocation_id
    assert restored.status == InvocationStatus.SUCCEEDED
    assert restored.output == {"value": 42}
    assert restored.metadata == {"source": "de-02"}

    with second._connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM ois_idempotency_results WHERE invocation_id = %s",
            (invocation_id,),
        )


def test_postgres_concurrent_duplicate_claim_has_one_winner():
    invocation_id = f"concurrent-{uuid4()}"

    def attempt(value: int) -> bool:
        store = PostgreSQLIdempotencyStore(POSTGRES_DSN)
        return store.put_if_absent(
            invocation_id,
            InvocationResult(
                invocation_id=invocation_id,
                capability_id="test.capability",
                status=InvocationStatus.SUCCEEDED,
                output={"winner": value},
            ),
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(attempt, range(12)))

    assert sum(outcomes) == 1

    store = PostgreSQLIdempotencyStore(POSTGRES_DSN)
    restored = store.get(invocation_id)
    assert restored is not None
    assert restored.output["winner"] in range(12)

    with store._connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM ois_idempotency_results WHERE invocation_id = %s",
            (invocation_id,),
        )
