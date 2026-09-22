from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    ExecutionStatus,
    PostgresDurableExecutionStore,
    SideEffectCommand,
    SideEffectResult,
    TransactionalSideEffectBoundary,
)


@pytest.fixture()
def postgres_store() -> PostgresDurableExecutionStore:
    dsn = os.getenv("OIS_POSTGRES_TEST_DSN")
    if not dsn:
        pytest.skip("OIS_POSTGRES_TEST_DSN is not configured")
    store = PostgresDurableExecutionStore(dsn)
    store.initialize()
    return store


def test_postgres_checkpoint_survives_new_connection(
    postgres_store: PostgresDurableExecutionStore,
) -> None:
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="test", workflow_id="durable-v1"),
        objective="postgres persistence",
        working_memory={"step": 3},
    )
    postgres_store.save(context)

    restored = postgres_store.load(context.identity.execution_id)

    assert restored.identity.execution_id == context.identity.execution_id
    assert restored.identity.tenant_id == "test"
    assert restored.working_memory == {"step": 3}


def test_postgres_does_not_store_failed_idempotency_result(
    postgres_store: PostgresDurableExecutionStore,
) -> None:
    from ois.kernel.contracts import InvocationResult
    from ois.kernel.types import InvocationStatus

    invocation_id = f"failure-{uuid4()}"
    result = InvocationResult(
        invocation_id=invocation_id,
        capability_id="side_effect.test",
        status=InvocationStatus.FAILED,
        error={"type": "transient"},
    )

    postgres_store.put_idempotency(invocation_id, uuid4(), "test", result)

    assert postgres_store.get_idempotency(invocation_id) is None


def test_outbox_reuses_idempotency_key_and_completes(
    postgres_store: PostgresDurableExecutionStore,
) -> None:
    boundary = TransactionalSideEffectBoundary(postgres_store._connect)
    execution_id = uuid4()
    invocation_id = f"effect-{uuid4()}"
    command = boundary.enqueue(
        tenant_id="test",
        execution_id=execution_id,
        invocation_id=invocation_id,
        capability_id="publish.test",
        idempotency_key=f"test:{invocation_id}",
        request={"message": "hello"},
    )

    claimed = boundary.claim(worker_id="test-worker")

    assert claimed is not None
    assert claimed == command
    assert claimed.idempotency_key == command.idempotency_key

    boundary.complete(
        command,
        SideEffectResult(
            effect_id=command.effect_id,
            idempotency_key=command.idempotency_key,
            output={"accepted": True},
            completed_at=datetime.now(UTC),
        ),
    )


def test_checkpoint_and_outbox_are_committed_as_one_transaction(
    postgres_store: PostgresDurableExecutionStore,
) -> None:
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="test", workflow_id="atomic"),
        objective="atomic checkpoint and effect intent",
        status=ExecutionStatus.EXECUTING,
    )
    command = SideEffectCommand(
        effect_id=str(uuid4()),
        tenant_id="test",
        execution_id=context.identity.execution_id,
        invocation_id=f"atomic-{uuid4()}",
        capability_id="publish.test",
        idempotency_key=f"publish:{context.identity.execution_id}:1",
        request={"payload": "x"},
    )

    postgres_store.commit_checkpoint_and_side_effect(context, command)

    assert postgres_store.load(context.identity.execution_id).status == ExecutionStatus.EXECUTING
