from __future__ import annotations

from ois.architecture.fabrics import (
    AgentWorkspace,
    ContextRequest,
    KnowledgeArtifact,
    LearningCandidate,
    LLMGatewaySpec,
    ModelRoute,
    ReasoningPattern,
    SocialSignal,
    WorkflowSpec,
    WorkerSpec,
)
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
