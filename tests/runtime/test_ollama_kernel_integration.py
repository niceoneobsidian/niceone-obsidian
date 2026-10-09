from __future__ import annotations

import json
from typing import Any

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
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
                "response": "OIS executed local inference through the Kernel.",
                "done": True,
            }
        ).encode("utf-8")


def test_ollama_inference_executes_through_kernel_fabric(
    monkeypatch: Any,
) -> None:
    requests: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: float) -> FakeOllamaResponse:
        requests.append(
            {
                "url": request.full_url,
                "payload": json.loads(request.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        return FakeOllamaResponse()

    monkeypatch.setattr("ois.runtime.ollama.urlopen", fake_urlopen)

    fabric_runtime = FabricRuntime()
    fabric_runtime.model_router.register(
        ModelRoute(
            ref_id="ollama-qwen3-local",
            provider="ollama",
            model="qwen3:8b",
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
    gateway.register_provider(
        "ollama",
        OllamaProvider(base_url="http://ollama:11434").invoke,
    )

    registry = CapabilityRegistry()
    register_fabric_capabilities(registry, fabric_runtime)
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=evidence,
    )
    context = ExecutionContext(
        identity=ExecutionIdentity(
            workflow_id="local-llm.workflow",
            workflow_version="1.0.0",
        ),
        objective="Run a local model through the governed OIS execution path",
    )

    result = runtime.execute(
        context,
        "fabric.llm.invoke",
        "1.0.0",
        {
            "prompt": "Explain OIS in one sentence.",
            "capabilities": ["text"],
        },
        invocation_id="ollama-kernel-integration-1",
    )

    assert result.status.value == "succeeded"
    assert result.output["response"] == "OIS executed local inference through the Kernel."
    assert requests == [
        {
            "url": "http://ollama:11434/api/generate",
            "payload": {
                "model": "qwen3:8b",
                "prompt": "Explain OIS in one sentence.",
                "stream": False,
            },
            "timeout": 120.0,
        }
    ]
    assert gateway.telemetry[-1]["provider"] == "ollama"
    assert gateway.telemetry[-1]["model"] == "qwen3:8b"
    assert gateway.telemetry[-1]["status"] == "succeeded"

    event_types = {event.event_type for event in evidence.list(context.identity.execution_id)}
    assert "execution.authorized" in event_types
    assert "execution.checkpointed" in event_types
    assert "capability.completed" in event_types
