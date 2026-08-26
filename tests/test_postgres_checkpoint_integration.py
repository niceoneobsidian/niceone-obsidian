from __future__ import annotations

import os

import pytest

from ois.kernel.postgres_checkpoint import PostgreSQLCheckpointStore
from ois.kernel.postgres_idempotency import PostgreSQLIdempotencyStore
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus


@pytest.mark.integration
def test_postgres_checkpoint_survives_new_store_instance() -> None:
    dsn = os.getenv("OIS_POSTGRES_DSN")
    if not dsn:
        pytest.skip("OIS_POSTGRES_DSN is not configured")

    import psycopg

    def connect() -> psycopg.Connection:
        return psycopg.connect(dsn)

    checkpoint = PostgreSQLCheckpointStore(connect)
    checkpoint.initialize()
    context = ExecutionContext(
        identity=ExecutionIdentity(workflow_id="durability-test", workflow_version="1"),
        objective="survive restart",
        status=ExecutionStatus.EXECUTING,
        current_node="node-2",
        working_memory={"completed": ["node-1"]},
    )
    checkpoint.save(context)

    restarted_store = PostgreSQLCheckpointStore(connect)
    restored = restarted_store.load(context.identity.execution_id)

    assert restored.identity.execution_id == context.identity.execution_id
    assert restored.current_node == "node-2"
    assert restored.status is ExecutionStatus.EXECUTING
    assert restored.working_memory == {"completed": ["node-1"]}


@pytest.mark.integration
def test_postgres_idempotency_survives_new_store_instance() -> None:
    dsn = os.getenv("OIS_POSTGRES_DSN")
    if not dsn:
        pytest.skip("OIS_POSTGRES_DSN is not configured")

    import psycopg

    def connect() -> psycopg.Connection:
        return psycopg.connect(dsn)

    from ois.kernel.contracts import InvocationResult
    from ois.kernel.types import InvocationStatus

    store = PostgreSQLIdempotencyStore(connect)
    store.initialize()
    result = InvocationResult(
        invocation_id="durability-idempotency-test",
        capability_id="test.capability",
        status=InvocationStatus.SUCCEEDED,
        output={"ok": True},
    )
    store.put(result.invocation_id, result)

    restarted_store = PostgreSQLIdempotencyStore(connect)
    restored = restarted_store.get(result.invocation_id)

    assert restored is not None
    assert restored.status is InvocationStatus.SUCCEEDED
    assert restored.output == {"ok": True}
