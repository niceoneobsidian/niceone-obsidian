"""Opt-in live Ollama + PostgreSQL durable vertical-slice test.

This test uses only a local Ollama endpoint and a dedicated test PostgreSQL DSN.
It never calls publishing, social, or other external write-capable integrations.
"""

from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities
from ois.runtime.ollama import OllamaProvider


@pytest.mark.live
def test_live_ollama_kernel_vertical_slice_is_durable() -> None:
    """Execute local inference, recreate the runtime, then replay without inference."""
    if os.getenv("OIS_LIVE_OLLAMA", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set OIS_LIVE_OLLAMA=1 to explicitly enable live Ollama inference")

    dsn = os.getenv("OIS_LIVE_DATABASE_URL", "").strip()
    if not dsn:
        pytest.skip("Set OIS_LIVE_DATABASE_URL to a dedicated disposable PostgreSQL test DB")

    model = os.getenv("OIS_OLLAMA_MODEL", "qwen2.5-coder:1.5b")
    connect = lambda: psycopg.connect(dsn)

    checkpoint_store = PostgresDurableExecutionStore(connect)
    checkpoint_store.initialize()
    idempotency_store = PostgresIdempotencyStore(connect)
    idempotency_store.initialize()
    evidence = PostgresEvidenceLedger(connect)
    evidence.initialize()

    fabric_runtime = FabricRuntime()
    fabric_runtime.model_router.register(
        ModelRoute(
            ref_id="ollama-live-local",
            provider="ollama",
            model=model,
            capabilities=("text",),
            cost_profile={"local": 0.0},
        )
    )
    gateway = fabric_runtime.configure_gateway(
        LLMGatewaySpec(
            ref_id="local-models",
            providers=("ollama",),
            fallback_policy="next_compatible",
        )
    )
    gateway.register_provider("ollama", OllamaProvider().invoke)

    registry = CapabilityRegistry()
    register_fabric_capabilities(registry, fabric_runtime)
    execution_id = uuid4()
    invocation_id = f"ollama-live-kernel-{uuid4()}"
    context = ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=execution_id,
            workflow_id="local-llm.live-workflow",
            workflow_version="1.0.0",
        ),
        objective="Verify local Ollama inference through the governed OIS Kernel",
    )
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store,
        evidence=evidence,
        idempotency=idempotency_store,
    )

    first = runtime.execute(
        context,
        "fabric.llm.invoke",
        "1.0.0",
        {
            "prompt": (
                "In two short sentences, explain what an autonomous "
                "operating system like OIS should do."
            ),
            "capabilities": ["text"],
        },
        invocation_id=invocation_id,
    )

    assert first.status.value == "succeeded", (
        f"Kernel execution failed for model {model!r}: {first.output!r}"
    )
    assert isinstance(first.output, dict)
    assert first.output.get("model") == model
    assert isinstance(first.output.get("response"), str)
    assert first.output["response"].strip()
    assert gateway.telemetry
    telemetry = gateway.telemetry[-1]
    assert telemetry["provider"] == "ollama"
    assert telemetry["model"] == model
    assert telemetry["status"] == "succeeded"

    checkpoint_store.close()
    idempotency_store.close()
    evidence.close()

    # Reopen each store and construct a fresh runtime to simulate process recreation.
    checkpoint_store_2 = PostgresDurableExecutionStore(connect)
    checkpoint_store_2.initialize()
    idempotency_store_2 = PostgresIdempotencyStore(connect)
    idempotency_store_2.initialize()
    evidence_2 = PostgresEvidenceLedger(connect)
    evidence_2.initialize()
    restored_context = checkpoint_store_2.load(execution_id)
    stored_events = evidence_2.list(execution_id)
    assert stored_events
    assert any(event.event_type == "capability.completed" for event in stored_events)
    telemetry_count = len(gateway.telemetry)

    runtime_2 = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store_2,
        evidence=evidence_2,
        idempotency=idempotency_store_2,
    )
    replay = runtime_2.execute(
        restored_context,
        "fabric.llm.invoke",
        "1.0.0",
        {
            "prompt": "This different prompt must not execute on replay.",
            "capabilities": ["text"],
        },
        invocation_id=invocation_id,
    )

    assert replay.status is first.status
    assert replay.output == first.output
    assert len(gateway.telemetry) == telemetry_count
    assert any(
        event.event_type == "execution.idempotency_hit"
        for event in evidence_2.list(execution_id)
    )
    assert len(evidence_2.list(execution_id)) > len(stored_events)

    checkpoint_store_2.close()
    idempotency_store_2.close()
    evidence_2.close()
