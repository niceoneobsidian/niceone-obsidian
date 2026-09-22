from datetime import UTC, datetime

from ois.domains.social_intelligence.graph import (
    SQLiteEvidenceGraph,
    canonical_hash,
    deterministic_entity_id,
)
from ois.domains.social_intelligence.pipeline import G1ResearchPipeline
from ois.infrastructure.source_gateway.outbox import OutboxEvent, SQLiteOutboxStore


def test_g1_e2e_outbox_to_research() -> None:
    outbox = SQLiteOutboxStore()
    graph = SQLiteEvidenceGraph()
    payload = {"topics": ["AI agents"], "text": "AI agents"}

    outbox.append(
        OutboxEvent(
            "evt",
            "tenant",
            "workspace",
            "source.raw_evidence.created",
            "e1",
            {
                "source_id": "source-a",
                "payload": payload,
                "payload_hash": canonical_hash(payload),
                "collected_at": datetime.now(UTC).isoformat(),
            },
            datetime.now(UTC),
        )
    )
    outbox.append(
        OutboxEvent(
            "evt2",
            "tenant",
            "workspace",
            "source.raw_evidence.created",
            "e2",
            {
                "source_id": "source-b",
                "payload": payload,
                "payload_hash": canonical_hash(payload),
                "collected_at": datetime.now(UTC).isoformat(),
            },
            datetime.now(UTC),
        )
    )

    pipeline = G1ResearchPipeline(outbox=outbox, graph=graph)
    report = pipeline.project_pending()
    assert report.consumed == 2
    assert report.projected >= 4
    assert graph.get_node(
        deterministic_entity_id("topic", "AI agents")
    ) is not None

    brief = pipeline.research(
        query="AI agents",
        tenant_id="tenant",
        workspace_id="workspace",
        entity_names=["AI agents"],
    )
    assert brief.confidence > 0
    assert len(brief.sources) == 2
    assert not outbox.pending()
