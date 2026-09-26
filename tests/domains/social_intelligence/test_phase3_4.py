from datetime import UTC, datetime

import pytest

from ois.domains.social_intelligence.graph import (
    GraphEdge,
    GraphNode,
    SQLiteEvidenceGraph,
    canonical_hash,
    deterministic_entity_id,
)
from ois.domains.social_intelligence.graph_ingestion import EvidenceGraphProjector
from ois.domains.social_intelligence.research import CrossSourceResearch
from ois.infrastructure.source_gateway.outbox import OutboxEvent


def evidence_node(evidence_id: str, source: str, text: str) -> GraphNode:
    payload = {"text": text, "topics": ["AI agents"]}
    return GraphNode(
        evidence_id,
        "evidence",
        "t",
        "w",
        source,
        payload,
        canonical_hash(payload),
        datetime.now(UTC),
    )


def test_graph_rejects_cross_scope_edges() -> None:
    graph = SQLiteEvidenceGraph()
    graph.upsert_node(evidence_node("e1", "tiktok", "AI agents"))
    graph.upsert_node(
        GraphNode(
            "e2",
            "entity",
            "other",
            "w",
            None,
            {"canonical_name": "AI agents"},
            "h",
            datetime.now(UTC),
        )
    )
    with pytest.raises(PermissionError):
        graph.add_edge(
            GraphEdge(
                "x",
                "t",
                "w",
                "e1",
                "e2",
                "mentions",
                0.9,
                (),
                datetime.now(UTC),
            )
        )


def test_outbox_projects_evidence_and_entity() -> None:
    graph = SQLiteEvidenceGraph()
    projector = EvidenceGraphProjector(graph)
    payload = {"topics": ["AI agents"]}
    event = OutboxEvent(
        "evt",
        "t",
        "w",
        "source.raw_evidence.created",
        "e1",
        {
            "source_id": "tiktok.display.v2",
            "payload": payload,
            "payload_hash": canonical_hash(payload),
            "collected_at": datetime.now(UTC).isoformat(),
        },
        datetime.now(UTC),
    )
    assert "e1" in projector.project(event)
    assert graph.get_node(
        deterministic_entity_id("topic", "AI agents")
    ) is not None


def test_cross_source_research_corroborates() -> None:
    graph = SQLiteEvidenceGraph()
    entity_id = deterministic_entity_id("topic", "AI agents")
    graph.upsert_node(
        GraphNode(
            entity_id,
            "entity",
            "t",
            "w",
            None,
            {"entity_type": "topic", "canonical_name": "AI agents"},
            "h",
            datetime.now(UTC),
        )
    )
    for index, source in enumerate(("tiktok.display.v2", "youtube")):
        node = evidence_node(f"e{index}", source, "AI agents")
        graph.upsert_node(node)
        graph.add_edge(
            GraphEdge(
                f"edge{index}",
                "t",
                "w",
                node.node_id,
                entity_id,
                "supports",
                0.9,
                (node.node_id,),
                datetime.now(UTC),
            )
        )
    findings = CrossSourceResearch(graph).corroboration(
        tenant_id="t",
        workspace_id="w",
        entity_id=entity_id,
    )
    assert findings[0].corroborated
    assert set(findings[0].source_ids) == {"tiktok.display.v2", "youtube"}
