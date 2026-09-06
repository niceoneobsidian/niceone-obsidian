from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.persistence import PostgreSQLCheckpointStore, RedisTransientCoordinator


@pytest.fixture()
def runtime_urls() -> tuple[str, str]:
    postgres_url = os.getenv("OIS_DATABASE_URL")
    redis_url = os.getenv("OIS_REDIS_URL")
    if not postgres_url or not redis_url:
        pytest.skip("OIS_DATABASE_URL and OIS_REDIS_URL are required for runtime conformance")
    return postgres_url, redis_url


def test_real_persistence_and_coordination_lifecycle(runtime_urls: tuple[str, str]) -> None:
    postgres_url, redis_url = runtime_urls
    postgres = PostgreSQLCheckpointStore(postgres_url)
    postgres.initialize()
    redis = RedisTransientCoordinator(redis_url)
    assert redis.ping()

    execution_id = uuid4()
    transaction_id = f"ois-test-{uuid4()}"
    state = ExecutionContext(
        identity=ExecutionIdentity(execution_id=execution_id, tenant_id="conformance"),
        objective="recovery conformance",
        metadata={"step_index": 0},
    )
    checkpoint_id = uuid4()
    owner = redis.acquire_execution_lock(str(execution_id), lock_timeout_sec=30)
    assert owner is not None
    assert redis.acquire_execution_lock(str(execution_id), lock_timeout_sec=30) is None

    try:
        postgres.save_checkpoint(checkpoint_id, state)
        recovered = postgres.fetch_last_valid_checkpoint(
            execution_id, tenant_id="conformance"
        )
        assert recovered is not None
        assert recovered.objective == state.objective
        assert recovered.identity.execution_id == execution_id

        result = {"status": "SUCCESS", "processed_records": 42}
        assert redis.cache_json_result(transaction_id, result)
        assert not redis.cache_json_result(transaction_id, {"status": "DUPLICATE"})
        cached = redis.check_idempotency_cache(transaction_id)
        assert cached is not None
        assert json.loads(cached)["processed_records"] == 42

        redis.set_cancellation_signal(str(execution_id), ttl_sec=30)
        assert redis.is_cancelled(str(execution_id))
        assert redis.clear_cancellation_signal(str(execution_id))
        assert not redis.is_cancelled(str(execution_id))
    finally:
        assert redis.release_execution_lock(str(execution_id), owner)
