import pytest

from ois.domains.social_intelligence.niche_genome import (
    GenomeConfig,
    NicheObservation,
    build_taxonomy_node,
    infer_intersection_edges,
    score_niche,
    slugify,
)


def test_slugify_is_stable() -> None:
    assert slugify("AI for Solo Founders") == "ai-for-solo-founders"


def test_taxonomy_node_is_candidate_by_default() -> None:
    node = build_taxonomy_node(
        node_id="gene-1",
        name="AI for Solo Founders",
        kind="gene",
        keywords=["AI", "founders", "AI"],
    )
    assert node.evidence_status == "candidate"
    assert node.keywords == ("ai", "founders")
    assert node.slug == "ai-for-solo-founders"


def test_niche_score_is_deterministic_and_bounded() -> None:
    observations = [
        NicheObservation(
            observation_id="o1", node_id="gene-1", source_id="reddit",
            platform="reddit", observed_at="2026-09-01T00:00:00Z",
            engagement_rate=0.4, viral_velocity=0.5, evidence_confidence=0.8,
        ),
        NicheObservation(
            observation_id="o2", node_id="gene-1", source_id="youtube",
            platform="youtube", observed_at="2026-09-02T00:00:00Z",
            engagement_rate=0.6, viral_velocity=0.7, evidence_confidence=0.9,
        ),
    ]
    result = score_niche("gene-1", observations, demand_score=0.7)
    assert result.sample_size == 2
    assert 0.0 <= result.opportunity_score <= 1.0
    assert result.opportunity_score == pytest.approx(0.69)


def test_custom_weights_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        GenomeConfig(demand_weight=0.5, engagement_weight=0.5, velocity_weight=0.5, evidence_weight=0.5)


def test_intersection_edges_are_candidates_not_validated_facts() -> None:
    nodes = [
        build_taxonomy_node(
            node_id="gene-1", name="AI for Founders", kind="gene",
            keywords=["ai", "founders", "automation"],
        ),
        build_taxonomy_node(
            node_id="gene-2", name="Automation for Startups", kind="gene",
            keywords=["automation", "startups"],
        ),
    ]
    edges = infer_intersection_edges(nodes)
    assert len(edges) == 1
    assert edges[0].kind == "intersects"
    assert edges[0].evidence_count == 0
    assert edges[0].confidence == 0.0
