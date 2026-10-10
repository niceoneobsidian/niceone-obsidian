from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import psycopg
import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.kernel.postgres import PostgresDurableExecutionStore
from ois.kernel.postgres_stores import PostgresEvidenceLedger, PostgresIdempotencyStore
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus, InvocationStatus
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities
from ois.runtime.ollama import OllamaProvider


class FakeOllamaResponse:
    def __enter__(self) -> FakeOllamaResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, *_args: object) -> bytes:
        return json.dumps(
            {
                "model": "qwen3:8b",
                "response": "OIS completed a durable local inference.",
                "done": True,
            }
        ).encode("utf-8")


def test_ollama_kernel_execution_persists_state_evidence_and_replays(
    migrated_postgres: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the governed Kernel→fabric→Ollama path with PostgreSQL-backed stores."""
    provider_calls: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeOllamaResponse:
        provider_calls.append(
            {
                "url": request.full_url,
                "payload": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return FakeOllamaResponse()

    monkeypatch.setattr("ois.runtime.ollama.urlopen", fake_urlopen)

    connection_factory = lambda: psycopg.connect(migrated_postgres)
    checkpoint_store = PostgresDurableExecutionStore(connection_factory)
    checkpoint_store.initialize()
    evidence_store = PostgresEvidenceLedger(connection_factory)
    evidence_store.initialize()
    idempotency_store = PostgresIdempotencyStore(connection_factory)
    idempotency_store.initialize()

    fabric_runtime = FabricRuntime()
    fabric_runtime.model_router.register(
        ModelRoute(
            ref_id="ollama-qwen3-durable",
            provider="ollama",
            model="qwen3:8b",
            capabilities=("text",),
            cost_profile={"local": 0.0},
        )
    )
    gateway = fabric_runtime.configure_gateway(
        LLMGatewaySpec(
            ref_id="durable-local-models",
            providers=("ollama",),
            fallback_policy="next_compatible",
        )
    )
    gateway.register_provider(
        "ollama",
        OllamaProvider(base_url="http://ollama:11434").invoke,
    )

    registry = CapabilityRegistry()
    register_fabric_capabilities(registry, fabric_runtime)
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=checkpoint_store,
        evidence=evidence_store,
        idempotency=idempotency_store,
    )

    identity = ExecutionIdentity(
        tenant_id="test-ollama-durable",
        workflow_id="ollama-durable.vertical-slice",
        workflow_version="1.0.0",
    )
    objective = "Run a local model through governed, durable OIS execution"
    input_data = {
        "prompt": "Explain OIS in one sentence.",
        "capabilities": ["text"],
    }
    invocation_id = f"ollama-durable-{uuid4()}"

    first_context = ExecutionContext(identity=identity, objective=objective)
    first = runtime.execute(
        first_context,
        "fabric.llm.invoke",
        "1.0.0",
        input_data,
        invocation_id=invocation_id,
    )

    assert first.status == InvocationStatus.SUCCEEDED
    assert first.output is not None
    assert first.output["response"] == "OIS completed a durable local inference."
    assert checkpoint_store.load(identity.execution_id).status == ExecutionStatus.COMPLETED
    assert idempotency_store.get(invocation_id) is not None

    event_types = {
        event.event_type for event in evidence_store.list(identity.execution_id)
    }
    assert {
        "execution.authorized",
        "execution.checkpointed",
        "capability.completed",
        "execution.completed",
    }.issubset(event_types)

    # A fresh context models a new runtime process replaying the same invocation.
    replay_context = ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=identity.execution_id,
            tenant_id=identity.tenant_id,
            workflow_id=identity.workflow_id,
            workflow_version=identity.workflow_version,
        ),
        objective=objective,
    )
    replay = runtime.execute(
        replay_context,
        "fabric.llm.invoke",
        "1.0.0",
        input_data,
        invocation_id=invocation_id,
    )

    assert replay.status == InvocationStatus.SUCCEEDED
    assert replay.output == first.output
    assert len(provider_calls) == 1
    assert provider_calls[0] == {
        "url": "http://ollama:11434/api/generate",
        "payload": {
            "model": "qwen3:8b",
            "prompt": "Explain OIS in one sentence.",
            "stream": False,
        },
        "timeout": 120.0,
    }
