"""Opt-in live test for real Ollama inference through the OIS Kernel."""

from __future__ import annotations

import os

import pytest

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities
from ois.runtime.ollama import OllamaProvider


@pytest.mark.live
def test_live_ollama_inference_executes_through_kernel_fabric() -> None:
    """Run real local inference only when explicitly enabled by the caller."""
    if os.getenv("OIS_LIVE_OLLAMA", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("Set OIS_LIVE_OLLAMA=1 to enable live Ollama inference")

    model = os.getenv("OIS_OLLAMA_MODEL", "qwen2.5-coder:1.5b")

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
    evidence = EvidenceLedger()
    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=evidence,
    )
    context = ExecutionContext(
        identity=ExecutionIdentity(
            workflow_id="local-llm.live-workflow",
            workflow_version="1.0.0",
        ),
        objective="Verify real local Ollama inference through the governed OIS Kernel",
    )

    result = runtime.execute(
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
        invocation_id="ollama-live-kernel-test",
    )

    assert result.status.value == "succeeded", (
        f"Kernel execution failed for model {model!r}: {result.output!r}"
    )
    assert isinstance(result.output, dict)
    assert result.output.get("model") == model
    assert isinstance(result.output.get("response"), str)
    assert result.output["response"].strip()

    assert gateway.telemetry
    telemetry = gateway.telemetry[-1]
    assert telemetry["provider"] == "ollama"
    assert telemetry["model"] == model
    assert telemetry["status"] == "succeeded"

    event_types = {
        event.event_type for event in evidence.list(context.identity.execution_id)
    }
    assert "execution.authorized" in event_types
    assert "execution.checkpointed" in event_types
    assert "capability.completed" in event_types
