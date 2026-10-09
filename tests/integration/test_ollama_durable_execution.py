"""Opt-in integration test for durable Ollama execution and replay after runtime restart."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.kernel.evidence import SQLiteEvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.persistence import (
    PostgreSQLCheckpointStore,
    RedisIdempotencyStore,
    RedisTransientCoordinator,
)
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities
from ois.runtime.ollama import OllamaProvider


def _register_ollama_fabric(
    model: str,
    provider_calls: list[str],
) -> tuple[CapabilityRegistry, FabricRuntime]:
    """Build a fresh runtime fabric while counting actual Ollama provider calls."""
    provider = OllamaProvider()
    fabric_runtime = FabricRuntime()
    fabric_runtime.model_router.register(
        ModelRoute(
            ref_id="ollama-durable-local",
            provider="ollama",
            model=model,
            capabilities=("text",),
            cost_profile={"local": 0.0},
        )
    )
    gateway = fabric_runtime.configure_gateway(
        LLMGatewaySpec(
            ref_id="local-models-durable",
            providers=("ollama",),
            fallback_policy="next_compatible",
        )
    )

    def counted_ollama(model_name: str, request: dict[str, Any]) -> dict[str, Any]:
        provider_calls.append(model_name)
        return provider.invoke(model_name, request)

    gateway.register_provider("ollama", counted_ollama)
    registry = CapabilityRegistry()
    register_fabric_capabilities(registry, fabric_runtime)
    return registry, fabric_runtime


@pytest.mark.integration
@pytest.mark.live
def test_live_ollama_durable_execution_replays_after_runtime_restart(
    tmp_path: Path,
) -> None:
    """Persist a real inference, restart runtime adapters, and prove replay is idempotent."""
    if os.getenv("OIS_LIVE_OLLAMA", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set OIS_LIVE_OLLAMA=1 to enable live Ollama inference")

    postgres_url = os.getenv("OIS_DATABASE_URL")
    redis_url = os.getenv("OIS_REDIS_URL")
    if not postgres_url or not redis_url:
        pytest.skip("OIS_DATABASE_URL and OIS_REDIS_URL are required for durable Ollama testing")

    model = os.getenv("OIS_OLLAMA_MODEL", "qwen2.5-coder:1.5b")
    postgres_first = PostgreSQLCheckpointStore(postgres_url)
    postgres_first.initialize()
    redis_first = RedisTransientCoordinator(redis_url)
    assert redis_first.ping()

    evidence_path = tmp_path / "ollama-durable-evidence.sqlite3"
    evidence_first = SQLiteEvidenceLedger(str(evidence_path))
    provider_calls: list[str] = []
    registry_first, fabric_first = _register_ollama_fabric(model, provider_calls)

    execution_id = uuid4()
    invocation_id = f"ollama-durable-{uuid4()}"
    context = ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=execution_id,
            tenant_id=str(uuid4()),
            workflow_id="local-llm.durable-replay",
            workflow_version="1.0.0",
        ),
        objective="Verify durable, governed Ollama inference and replay protection",
    )
    runtime_first = ExecutionRuntime(
        registry=registry_first,
        checkpoint_store=postgres_first,
        evidence=evidence_first,
        idempotency=RedisIdempotencyStore(redis_first),
    )

    try:
        first_result = runtime_first.execute(
            context,
            "fabric.llm.invoke",
            "1.0.0",
            {
                "prompt": (
                    "In two short sentences, explain how OIS should govern an autonomous "
                    "operating system."
                ),
                "capabilities": ["text"],
            },
            invocation_id=invocation_id,
        )

        assert first_result.status.value == "succeeded", (
            f"Kernel execution failed for model {model!r}: {first_result.output!r}"
        )
        assert isinstance(first_result.output, dict)
        assert first_result.output.get("model") == model
        assert isinstance(first_result.output.get("response"), str)
        assert first_result.output["response"].strip()
        assert provider_calls == [model]
        assert fabric_first.llm_gateway is not None
        assert len(fabric_first.llm_gateway.telemetry) == 1
        assert postgres_first.load(execution_id).identity.execution_id == execution_id
        assert any(
            event.event_type == "execution.checkpointed"
            for event in evidence_first.list(execution_id)
        )
    finally:
        evidence_first.close()

    # Reopen every persistence adapter and construct a fresh fabric/runtime, as a
    # restarted worker would. The loaded checkpoint retains the execution identity.
    postgres_second = PostgreSQLCheckpointStore(postgres_url)
    redis_second = RedisTransientCoordinator(redis_url)
    assert redis_second.ping()
    evidence_second = SQLiteEvidenceLedger(str(evidence_path))
    registry_second, fabric_second = _register_ollama_fabric(model, provider_calls)
    recovered_context = postgres_second.load(execution_id)
    runtime_second = ExecutionRuntime(
        registry=registry_second,
        checkpoint_store=postgres_second,
        evidence=evidence_second,
        idempotency=RedisIdempotencyStore(redis_second),
    )

    try:
        # Deliberately change the prompt: an idempotency hit must return the first
        # terminal result, not execute the capability using this new input.
        replay_result = runtime_second.execute(
            recovered_context,
            "fabric.llm.invoke",
            "1.0.0",
            {
                "prompt": "This changed prompt must not trigger another Ollama call.",
                "capabilities": ["text"],
            },
            invocation_id=invocation_id,
        )

        assert replay_result.status == first_result.status
        assert replay_result.output == first_result.output
        assert provider_calls == [model], "Ollama was invoked again during replay"
        assert fabric_second.llm_gateway is not None
        assert fabric_second.llm_gateway.telemetry == []

        # Evidence from the first process must survive closing/reopening SQLite,
        # and the second process must append a durable idempotency-hit event.
        events = evidence_second.list(execution_id)
        event_types = [event.event_type for event in events]
        assert "execution.received" in event_types
        assert "execution.authorized" in event_types
        assert "execution.checkpointed" in event_types
        assert event_types.count("execution.idempotency_hit") == 1
        assert event_types.count("execution.received") == 1
        assert event_types.count("capability.completed") == 1
    finally:
        evidence_second.close()
        redis_first.client.close()
        redis_second.client.close()
