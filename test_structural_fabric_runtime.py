from __future__ import annotations

from ois.architecture.fabrics import (
    AgentWorkspace,
    ContextRequest,
    KnowledgeArtifact,
    LLMGatewaySpec,
    LearningCandidate,
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
    runtime.bind_agent(AgentWorkspace("workspace", agent_id="agent-1"))

    started = runtime.workflow.start("wf", "exec-1", {"topic": "OIS"})
    runtime.workflow.checkpoint("exec-1", "research", {"ok": True})
    resumed = runtime.workflow.resume("exec-1")
    session = runtime.agents.open_session("agent-1", "session-1")

    assert started["status"] == "ready"
    assert "research" in resumed["completed_nodes"]
    assert session["agent_id"] == "agent-1"


def test_llm_gateway_routes_to_registered_provider() -> None:
    runtime = FabricRuntime()
    runtime.model_router.register(
        ModelRoute(
            "route",
            provider="test",
            model="model-a",
            capabilities=("chat",),
        )
    )
    gateway = runtime.configure_gateway(
        LLMGatewaySpec("gateway", providers=("test",))
    )
    gateway.register_provider(
        "test",
        lambda model, payload: {
            "model": model,
            "text": payload["prompt"],
        },
    )

    result = gateway.invoke("hello", capabilities={"chat"})
    assert result == {"model": "model-a", "text": "hello"}


def test_context_knowledge_reasoning_social_and_learning() -> None:
    runtime = FabricRuntime()
    runtime.bind_knowledge(
        KnowledgeArtifact(
            "doc-1",
            source_ref="source",
            content_ref="OIS social intelligence",
            metadata={"topic": "social"},
        )
    )
    runtime.context.knowledge["doc-1"] = {"title": "OIS"}
    runtime.bind_reasoning(
        ReasoningPattern(
            "reflection",
            objective_classes=("analysis",),
            topology="loop",
        )
    )
    runtime.bind_social(
        SocialSignal(
            "sig-1",
            platform="tiktok",
            topic_refs=("ai",),
            signal_type="mention",
            value=12,
            confidence=0.9,
        )
    )

    context = runtime.bind_context(
        ContextRequest(
            "ctx",
            objective="analyze",
            knowledge_refs=("doc-1",),
        )
    )
    result = runtime.reasoning.select("analysis")
    social = runtime.social.query(platform="tiktok", topic="ai")

    assert context["knowledge"] == [{"title": "OIS"}]
    assert result.ref_id == "reflection"
    assert len(social) == 1

    runtime.bind_learning(
        LearningCandidate(
            "candidate-1",
            hypothesis="improve hook",
            evidence_refs=("eval-1",),
        )
    )
    promoted = runtime.learning.promote(
        "candidate-1",
        approved=True,
        evidence_refs=("approval-1",),
    )
    assert promoted.promotion_state == "approved"


def test_kernel_registry_exposes_fabric_capabilities() -> None:
    runtime = FabricRuntime()
    registry = CapabilityRegistry()
    ids = register_fabric_capabilities(registry, runtime)

    assert "fabric.workflow" in ids
    assert "fabric.llm.invoke" in ids
    assert registry.has("fabric.agent.session", "1.0.0")
