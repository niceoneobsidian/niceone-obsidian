from datetime import UTC, datetime

from ois.domains.social_intelligence.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_intelligence.runtime_capabilities import (
    M14ContentIntelligence,
    M15Prediction,
    M16Experimentation,
    M17Learning,
    M18ViralPatternLearning,
    M19CampaignOptimization,
    M20ControlledEvolution,
)
from ois.domains.social_intelligence.runtime_registry import register_social_runtime
from ois.kernel.contracts import InvocationRequest
from ois.kernel.registry import AgentRegistry, CapabilityRegistry, ToolRegistry
from ois.kernel.state import ExecutionContext, ExecutionIdentity


def _request(capability_id: str, payload: dict) -> InvocationRequest:
    return InvocationRequest(
        invocation_id="test-invocation",
        capability_id=capability_id,
        input=payload,
        execution=ExecutionContext(
            identity=ExecutionIdentity(tenant_id="test", workflow_id="social", workflow_version="1"),
            objective="social test",
        ),
    )


def test_all_m14_m20_capabilities_are_kernel_contracts() -> None:
    expected = {
        "social.content.intelligence": M14ContentIntelligence,
        "social.content.predict": M15Prediction,
        "social.experiment.simulate": M16Experimentation,
        "social.learning.compare_outcome": M17Learning,
        "social.learning.pattern_extract": M18ViralPatternLearning,
        "social.campaign.optimize": M19CampaignOptimization,
        "social.evolution.propose": M20ControlledEvolution,
    }
    for capability_id, provider in expected.items():
        assert provider().contract.capability_id == capability_id
        assert provider().contract.version == "1.0.0"


def test_social_runtime_registers_m13_to_m20_and_platform_tools() -> None:
    connectors = ConnectorRegistry()
    connectors.register(GenericSocialConnector("test-platform", lambda intent: {"id": "p1"}))
    capabilities = CapabilityRegistry()
    agents = AgentRegistry()
    tools = ToolRegistry()

    counts = register_social_runtime(capabilities, agents, tools, connectors=connectors)

    assert counts == {"capabilities": 9, "agents": 9, "tools": 1}
    assert capabilities.has("social.ingest", "1.1.0")
    assert capabilities.has("social.research.execute", "1.0.0")
    assert capabilities.has("social.content.intelligence", "1.0.0")
    assert capabilities.has("social.evolution.propose", "1.0.0")
    assert tools.has("social.tool.test-platform.publish", "1.0.0")


def test_m14_to_m17_execute_without_platform_side_effects() -> None:
    request = _request(
        "social.content.intelligence",
        {
            "content_id": "c1",
            "observations": [
                {"modality": "text", "features": {"hook": {"strength": 0.9, "curiosity": 0.8}}},
                {"modality": "video", "features": {"temporal": {"pacing": 0.75}}},
            ],
        },
    )
    genome_result = M14ContentIntelligence().invoke(request)
    genome = genome_result.output["content_genome"]
    prediction = M15Prediction().invoke(_request("social.content.predict", {"content_genome": genome}))
    assert prediction.output["prediction"]["model_version"] == "m15.v1"

    scores = M16Experimentation().invoke(_request("social.experiment.simulate", {
        "experiment_id": "e1", "objective": "retention", "hypothesis": "stronger hook wins",
        "control_variant_id": "b",
        "variants": [
            {"variant_id": "a", "genome": genome, "hypothesis": "stronger hook"},
            {"variant_id": "b", "genome": {**genome, "content_id": "c2", "hook": {"strength": 0.2}}, "hypothesis": "control"},
        ],
    }))
    assert scores.output["scores"]

    observed = {"metrics": {"overall_performance": 0.8}, "source": "test.analytics", "observed_at": datetime.now(UTC).isoformat()}
    learning = M17Learning().invoke(_request("social.learning.compare_outcome", {
        "content_id": "c1", "prediction_version": prediction.output["prediction"]["model_version"],
        "predicted": prediction.output["prediction"]["metrics"], "observed": observed,
        "evidence_refs": ["test:evidence"],
    }))
    assert learning.output["learning_event"]["evidence_refs"] == ["test:evidence"]


def test_m18_m20_are_evidence_gated_and_non_mutating() -> None:
    empty = M18ViralPatternLearning().invoke(_request("social.learning.pattern_extract", {
        "content_id": "c1", "patterns": [{"type": "hook", "value": "curiosity"}], "learning_event": {}
    }))
    assert empty.output["candidates"] == []

    candidate = M20ControlledEvolution().invoke(_request("social.evolution.propose", {
        "hypothesis": "increase retention by changing hook", "evidence_refs": ["learning:1"],
        "target": {"capability": "social.content.predict"},
    }))
    assert candidate.output["candidate"]["production_mutation"] is False
