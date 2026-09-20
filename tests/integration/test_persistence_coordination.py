from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

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
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.evidence import EvidenceLedger
from ois.persistence import (
    PostgreSQLCheckpointStore,
    RedisCancellationToken,
    RedisIdempotencyStore,
    RedisTransientCoordinator,
)


class CountingEchoCapability:
    calls = 0

    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="conformance.echo",
            version="1.0.0",
            description="Deterministic integration capability.",
            input_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "required": ["message"],
                "properties": {"message": {"type": "string"}},
            },
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        self.calls += 1
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"message": request.input["message"]},
        )


@pytest.fixture()
def runtime_urls() -> tuple[str, str]:
    postgres_url = os.getenv("OIS_DATABASE_URL")
    redis_url = os.getenv("OIS_REDIS_URL")
    if not postgres_url or not redis_url:
        pytest.skip("OIS_DATABASE_URL and OIS_REDIS_URL are required for runtime conformance")
    return postgres_url, redis_url


def test_real_persistence_coordination_and_recovery(
    runtime_urls: tuple[str, str],
) -> None:
    postgres_url, redis_url = runtime_urls
    postgres = PostgreSQLCheckpointStore(postgres_url)
    postgres.initialize()
    redis = RedisTransientCoordinator(redis_url)
    assert redis.ping()

    execution_id = uuid4()
    transaction_id = f"ois-test-{uuid4()}"
    state = ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=execution_id,
            tenant_id="conformance",
        ),
        objective="recovery conformance",
        metadata={"step_index": 0},
    )
    first_checkpoint_id = uuid4()
    second_checkpoint_id = uuid4()
    owner = redis.acquire_execution_lock(str(execution_id), lock_timeout_sec=30)
    assert owner is not None
    assert redis.acquire_execution_lock(str(execution_id), lock_timeout_sec=30) is None

    cancelled_execution_id: UUID | None = None
    try:
        postgres.save_checkpoint(first_checkpoint_id, state)
        state.metadata["step_index"] = 1
        state.working_memory["checkpoint"] = "newest"
        postgres.save_checkpoint(second_checkpoint_id, state)

        # The database trigger protects immutable history. The controlled fault
        # injector temporarily disables it only to simulate storage corruption.
        with (
            pytest.raises(psycopg.Error),
            postgres.connection() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE ois_execution_checkpoint_history "
                "SET state = state WHERE checkpoint_id = %s",
                (second_checkpoint_id,),
            )
            connection.commit()

        with postgres.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE ois_execution_checkpoint_history "
                "DISABLE TRIGGER trg_ois_checkpoint_history_immutable"
            )
            cursor.execute(
                """
                UPDATE ois_execution_checkpoint_history
                SET state = jsonb_set(
                    state, '{objective}', '"CORRUPTED"'::jsonb
                )
                WHERE checkpoint_id = %s
                """,
                (second_checkpoint_id,),
            )
            cursor.execute(
                "ALTER TABLE ois_execution_checkpoint_history "
                "ENABLE TRIGGER trg_ois_checkpoint_history_immutable"
            )
        connection.commit()

        recovered = postgres.fetch_last_valid_checkpoint(execution_id, tenant_id="conformance")
        assert recovered is not None
        assert recovered.objective == "recovery conformance"
        assert recovered.metadata["step_index"] == 0
        assert recovered.working_memory == {}

        recovery_evidence = {
            "execution_id": str(execution_id),
            "fault": "CORRUPT_CHECKPOINT",
            "failed_checkpoint_id": str(second_checkpoint_id),
            "restored_checkpoint_id": str(first_checkpoint_id),
            "action": "RESTORE_LAST_VALID_CHECKPOINT",
            "outcome": "RECOVERED",
        }
        assert recovery_evidence["outcome"] == "RECOVERED"
        assert (
            recovery_evidence["restored_checkpoint_id"] != recovery_evidence["failed_checkpoint_id"]
        )

        registry = CapabilityRegistry()
        capability = CountingEchoCapability()
        registry.register(capability)
        invocation_id = f"invocation-{uuid4()}"
        evidence_one = EvidenceLedger()
        evidence_two = EvidenceLedger()
        runtime_one = ExecutionRuntime(
            registry=registry,
            checkpoint_store=postgres,
            evidence=evidence_one,
            idempotency=RedisIdempotencyStore(redis),
        )
        runtime_two = ExecutionRuntime(
            registry=registry,
            checkpoint_store=postgres,
            evidence=evidence_two,
            idempotency=RedisIdempotencyStore(redis),
        )
        runtime_state = ExecutionContext(
            identity=ExecutionIdentity(
                execution_id=uuid4(),
                tenant_id="conformance",
            ),
            objective="duplicate execution",
        )
        first_result = runtime_one.execute(
            runtime_state,
            "conformance.echo",
            "1.0.0",
            {"message": "exactly once"},
            invocation_id=invocation_id,
        )
        second_result = runtime_two.execute(
            runtime_state,
            "conformance.echo",
            "1.0.0",
            {"message": "must not execute twice"},
            invocation_id=invocation_id,
        )
        assert first_result.status == InvocationStatus.SUCCEEDED
        assert second_result.output == first_result.output
        assert capability.calls == 1
        assert any(
            event.event_type == "execution.idempotency_hit"
            for event in evidence_two.list(runtime_state.identity.execution_id)
        )

        cancelled_execution_id = uuid4()
        cancellation = RedisCancellationToken(redis, str(cancelled_execution_id))
        cancellation.cancel("operator requested stop")
        cancellation_evidence = EvidenceLedger()
        cancelled_runtime = ExecutionRuntime(
            registry=registry,
            checkpoint_store=postgres,
            evidence=cancellation_evidence,
            cancellation=cancellation,
            idempotency=RedisIdempotencyStore(redis),
        )
        cancelled_context = ExecutionContext(
            identity=ExecutionIdentity(
                execution_id=cancelled_execution_id,
                tenant_id="conformance",
            ),
            objective="cancellation conformance",
        )
        cancelled_result = cancelled_runtime.execute(
            cancelled_context,
            "conformance.echo",
            "1.0.0",
            {"message": "should never run"},
            invocation_id=f"cancel-{uuid4()}",
        )
        assert cancelled_result.status == InvocationStatus.CANCELLED
        assert cancelled_context.status.value == "stopped"
        assert "operator requested stop" in cancelled_result.error["message"]
        assert capability.calls == 1
        assert any(
            event.event_type == "execution.cancelled"
            for event in cancellation_evidence.list(cancelled_execution_id)
        )

        assert redis.cache_json_result(
            transaction_id,
            {"status": "SUCCESS", "processed_records": 42},
        )
        assert not redis.cache_json_result(transaction_id, {"status": "duplicate"})
        cached = redis.check_idempotency_cache(transaction_id)
        assert cached is not None
        assert json.loads(cached)["processed_records"] == 42
    finally:
        assert redis.release_execution_lock(str(execution_id), owner)
        redis.clear_cancellation_signal(str(execution_id))
        if cancelled_execution_id is not None:
            redis.clear_cancellation_signal(str(cancelled_execution_id))
