from ois.domains.social_intelligence.niche_kernel import (
    NicheScoringCapability,
    NicheTaxonomyCapability,
    register_niche_genome_capabilities,
)
from ois.kernel.contracts import InvocationRequest
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.state import ExecutionContext, ExecutionIdentity


def _request(capability_id: str, payload: dict[str, object]) -> InvocationRequest:
    return InvocationRequest(
        invocation_id="invocation-1",
        capability_id=capability_id,
        input=payload,
        execution=ExecutionContext(
            identity=ExecutionIdentity(tenant_id="test"),
            objective="social genome test",
        ),
    )


def test_niche_capabilities_expose_authoritative_contracts() -> None:
    taxonomy = NicheTaxonomyCapability()
    scoring = NicheScoringCapability()
    assert taxonomy.contract.capability_id == "social.genome.taxonomy.build"
    assert scoring.contract.capability_id == "social.genome.niche.score"
    assert taxonomy.contract.idempotent
    assert scoring.contract.idempotent


def test_taxonomy_capability_is_executable_without_external_side_effects() -> None:
    result = NicheTaxonomyCapability().invoke(
        _request(
            "social.genome.taxonomy.build",
            {
                "nodes": [
                    {
                        "node_id": "g1",
                        "name": "AI Founders",
                        "kind": "gene",
                        "keywords": ["ai", "founders"],
                    },
                    {
                        "node_id": "g2",
                        "name": "AI Automation",
                        "kind": "gene",
                        "keywords": ["ai", "automation"],
                    },
                ]
            },
        )
    )
    assert result.status.value == "succeeded"
    assert len(result.output["nodes"]) == 2
    assert len(result.output["intersection_edges"]) == 1


def test_scoring_capability_is_executable() -> None:
    result = NicheScoringCapability().invoke(
        _request(
            "social.genome.niche.score",
            {
                "node_id": "g1",
                "demand_score": 0.8,
                "observations": [
                    {
                        "observation_id": "o1",
                        "node_id": "g1",
                        "source_id": "reddit",
                        "platform": "reddit",
                        "observed_at": "2026-09-01T00:00:00Z",
                        "engagement_rate": 0.5,
                        "viral_velocity": 0.4,
                        "evidence_confidence": 0.9,
                    }
                ],
            },
        )
    )
    assert result.status.value == "succeeded"
    assert 0.0 <= result.output["score"]["opportunity_score"] <= 1.0


def test_registration_uses_existing_registry() -> None:
    registry = CapabilityRegistry()
    register_niche_genome_capabilities(registry)
    assert registry.has("social.genome.taxonomy.build", "1.0.0")
    assert registry.has("social.genome.niche.score", "1.0.0")
