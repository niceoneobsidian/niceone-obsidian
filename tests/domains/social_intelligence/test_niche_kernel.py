from ois.domains.social_intelligence.niche_kernel import (
    NicheScoringCapability,
    NicheTaxonomyCapability,
    register_niche_genome_capabilities,
)
from ois.kernel.contracts import InvocationRequest
from ois.kernel.registry import CapabilityRegistry


def test_niche_capabilities_expose_authoritative_contracts() -> None:
    taxonomy = NicheTaxonomyCapability()
    scoring = NicheScoringCapability()
    assert taxonomy.contract.capability_id == "social.genome.taxonomy.build"
    assert scoring.contract.capability_id == "social.genome.niche.score"
    assert taxonomy.contract.idempotent
    assert scoring.contract.idempotent


def test_taxonomy_capability_is_executable_without_external_side_effects() -> None:
    result = NicheTaxonomyCapability().invoke(
        InvocationRequest(
            input={
                "nodes": [
                    {"node_id": "g1", "name": "AI Founders", "kind": "gene", "keywords": ["ai", "founders"]},
                    {"node_id": "g2", "name": "AI Automation", "kind": "gene", "keywords": ["ai", "automation"]},
                ]
            }
        )
    )
    assert result.status.value == "succeeded"
    assert len(result.output["nodes"]) == 2
    assert len(result.output["intersection_edges"]) == 1


def test_scoring_capability_is_executable() -> None:
    result = NicheScoringCapability().invoke(
        InvocationRequest(
            input={
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
            }
        )
    )
    assert result.status.value == "succeeded"
    assert 0.0 <= result.output["score"]["opportunity_score"] <= 1.0


def test_registration_uses_existing_registry() -> None:
    registry = CapabilityRegistry()
    register_niche_genome_capabilities(registry)
    assert registry.get("social.genome.taxonomy.build") is not None
    assert registry.get("social.genome.niche.score") is not None
