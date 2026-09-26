from datetime import UTC, datetime

from ois.domains.social_intelligence.graph import (
    SQLiteEvidenceGraph,
    deterministic_entity_id,
)
from ois.domains.social_intelligence.pipeline import G1ResearchPipeline
from ois.infrastructure.source_gateway import SQLiteSourceLedger
from ois.infrastructure.source_gateway.evidence import canonical_hash
from ois.infrastructure.source_gateway.outbox import OutboxEvent


def _ingest(
    ledger: SQLiteSourceLedger,
    event_id: str,
    evidence_id: str,
    source_id: str,
) -> None:
    from ois.infrastructure.source_gateway.evidence import RawEvidence

    payload = {"topics": ["AI agents"], "text": "AI agents"}
    evidence = RawEvidence(
        evidence_id=evidence_id,
        tenant_id="tenant",
        workspace_id="workspace",
        source_id=source_id,
        source_record_id=evidence_id,
        payload=payload,
        payload_hash=canonical_hash(payload),
        collected_at=datetime.now(UTC),
        connector_version="test",
        schema_version="test",
        ingestion_run_id="run",
    )
    ledger.commit_ingest(
        evidence,
        OutboxEvent(
            event_id,
            "tenant",
            "workspace",
            "source.raw_evidence.created",
            evidence_id,
            {
                "source_id": source_id,
                "payload_hash": evidence.payload_hash,
            },
            datetime.now(UTC),
        ),
    )


def test_g1_e2e_outbox_to_research() -> None:
    ledger = SQLiteSourceLedger()
    _ingest(ledger, "evt", "e1", "source-a")
    _ingest(ledger, "evt2", "e2", "source-b")
    graph = SQLiteEvidenceGraph()
    pipeline = G1ResearchPipeline(
        outbox=ledger,
        graph=graph,
        evidence_reader=ledger,
    )

    report = pipeline.project_pending()
    assert report.consumed == 2
    assert report.projected >= 4
    assert (
        graph.get_node(deterministic_entity_id("topic", "AI agents")) is not None
    )

    brief = pipeline.research(
        query="AI agents",
        tenant_id="tenant",
        workspace_id="workspace",
        entity_names=["AI agents"],
    )
    assert brief.confidence > 0
    assert len(brief.sources) == 2
    assert not ledger.pending()
