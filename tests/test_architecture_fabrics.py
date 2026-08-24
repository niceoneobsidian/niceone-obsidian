from ois.architecture.fabrics import (
    AgentWorkspace,
    FabricKind,
    FabricSpec,
    InMemoryFabricRegistry,
    LLMGatewaySpec,
    LearningCandidate,
    SocialSignal,
    WorkflowSpec,
)


def test_registry_is_versioned_and_kind_filterable() -> None:
    registry = InMemoryFabricRegistry()
    registry.register(FabricSpec("workflow", FabricKind.WORKFLOW))
    registry.register(FabricSpec("social", FabricKind.SOCIAL))

    assert registry.get("workflow") is not None
    assert [item.fabric_id for item in registry.list(FabricKind.SOCIAL)] == ["social"]


def test_workflow_is_durable_by_contract() -> None:
    workflow = WorkflowSpec("growth", nodes=("research", "create", "validate"))
    assert workflow.checkpointable
    assert workflow.resumable


def test_gateway_requires_explicit_routing_contract() -> None:
    gateway = LLMGatewaySpec("gateway", providers=("openai", "anthropic", "local"))
    assert gateway.routing_policy == "capability_first"
    assert gateway.retry_policy == "bounded"
    assert gateway.structured_output


def test_agent_workspace_isolated_by_identity_and_policy() -> None:
    workspace = AgentWorkspace(
        "agent-workspace",
        agent_id="social-researcher",
        identity_ref="agent:researcher",
        policy_refs=("policy:social-read",),
    )
    assert workspace.agent_id == "social-researcher"
    assert workspace.policy_refs == ("policy:social-read",)


def test_social_signal_preserves_provenance_and_confidence() -> None:
    signal = SocialSignal(
        "signal-1",
        source_ref="source:tiktok",
        platform="tiktok",
        signal_type="trend_velocity",
        value=0.82,
        confidence=0.91,
    )
    assert signal.source_ref == "source:tiktok"
    assert signal.confidence == 0.91


def test_learning_candidate_cannot_claim_promotion_by_default() -> None:
    candidate = LearningCandidate("candidate-1", hypothesis="improve_hook")
    assert candidate.promotion_state == "candidate"
