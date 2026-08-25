from __future__ import annotations

from ois.architecture.fabrics import AgentWorkspace, WorkflowSpec, WorkerSpec
from ois.kernel.registry import CapabilityRegistry
from ois.runtime.fabrics import FabricRuntime, register_fabric_capabilities


def test_workflow_worker_and_agent_runtime_bindings() -> None:
    runtime = FabricRuntime()
    runtime.bind_workflow(
        WorkflowSpec(
            "wf",
            nodes=("research", "write"),
            edges=(("research", "write"),),
        )
    )
    runtime.bind_worker(
        WorkerSpec(
            "worker",
            queue="default",
            concurrency=2,
            max_attempts=2,
        )
    )
    runtime.bind_agent(AgentWorkspace("workspace", agent_id="agent-1"))

    started = runtime.workflow.start("wf", "exec-1", {"topic": "OIS"})
    runtime.workflow.checkpoint("exec-1", "research", {"ok": True})
    resumed = runtime.workflow.resume("exec-1")

    assert started["workflow_id"] == "wf"
    assert started["execution_id"] == "exec-1"
    assert resumed["execution_id"] == "exec-1"


def test_structural_fabric_capabilities_register() -> None:
    registry = CapabilityRegistry()
    runtime = FabricRuntime()
    register_fabric_capabilities(registry, runtime)

    assert registry.resolve("fabric.workflow", "1.0.0") is not None
    assert registry.resolve("fabric.worker", "1.0.0") is not None
    assert registry.resolve("fabric.agent", "1.0.0") is not None
    assert registry.resolve("fabric.model", "1.0.0") is not None
    assert registry.resolve("fabric.llm", "1.0.0") is not None
    assert registry.resolve("fabric.knowledge", "1.0.0") is not None
    assert registry.resolve("fabric.context", "1.0.0") is not None
    assert registry.resolve("fabric.reasoning", "1.0.0") is not None
    assert registry.resolve("fabric.social", "1.0.0") is not None
    assert registry.resolve("fabric.learning", "1.0.0") is not None
