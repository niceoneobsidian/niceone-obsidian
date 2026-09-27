from __future__ import annotations

from datetime import UTC, datetime

from ois.domains.social_intelligence.postgres_store import PostgresSocialSliceStore
from ois.domains.social_intelligence.schemas import SocialPost
from ois.infrastructure.source_gateway.evidence import RawEvidence, canonical_hash
from ois.infrastructure.source_gateway.outbox import OutboxEvent
from ois.infrastructure.source_gateway.postgres import PostgresSourceLedger
from tests.helpers.migrations import apply_migrations


def test_social_intelligence_migration_is_idempotent(postgres_connection, migrated_postgres):
    apply_migrations(postgres_connection, __import__("pathlib").Path("migrations"))
    with postgres_connection.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
              AND table_name IN (
                'raw_evidence',
                'source_outbox',
                'publication_ledger',
                'social_intelligence_posts'
              )
            ORDER BY table_name
            """
        )
        assert [row[0] for row in cur.fetchall()] == [
            "publication_ledger",
            "raw_evidence",
            "social_intelligence_posts",
            "source_outbox",
        ]


def test_social_posts_are_tenant_scoped(postgres_connection):
    store = PostgresSocialSliceStore(postgres_connection)
    post = SocialPost(
        provider="tiktok_display_v2",
        platform="tiktok",
        external_id="video-1",
        text="hello",
        observed_at=datetime.now(UTC),
    )
    store.upsert_posts((post,), tenant_id="tenant-a", workspace_id="workspace-a")

    assert (
        store.get(
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            external_id="video-1",
        )
        is not None
    )
    assert (
        store.get(
            tenant_id="tenant-b",
            workspace_id="workspace-b",
            external_id="video-1",
        )
        is None
    )


def test_publication_ledger_is_idempotent(postgres_connection):
    ledger = PostgresSourceLedger(postgres_connection)
    assert ledger.record_publication(
        publication_id="pub-1",
        event_id="event-1",
        destination="social-intelligence",
        idempotency_key="tenant-a:video-1",
    )
    assert not ledger.record_publication(
        publication_id="pub-2",
        event_id="event-2",
        destination="social-intelligence",
        idempotency_key="tenant-a:video-1",
    )
    publication = ledger.publication(
        destination="social-intelligence",
        idempotency_key="tenant-a:video-1",
    )
    assert publication is not None
    assert publication["publication_id"] == "pub-1"


def test_duplicate_ingestion_repairs_missing_outbox(postgres_connection):
    ledger = PostgresSourceLedger(postgres_connection)
    payload = {"data": {"videos": [{"id": "repair-1"}]}}
    evidence = RawEvidence(
        evidence_id="evidence-repair-1",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        source_id="tiktok.display.v2",
        source_record_id="cursor:initial",
        payload=payload,
        payload_hash=canonical_hash(payload),
        collected_at=datetime.now(UTC),
        connector_version="tiktok-display-v2",
        schema_version="tiktok.display.v2",
        ingestion_run_id="run-repair-1",
    )
    event = OutboxEvent(
        event_id="event-repair-1",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        event_type="source.raw_evidence.created",
        aggregate_id=evidence.evidence_id,
        payload={"evidence_id": evidence.evidence_id},
        created_at=datetime.now(UTC),
    )

    assert ledger.commit_ingest(evidence, event)
    with postgres_connection.cursor() as cur:
        cur.execute("DELETE FROM source_outbox WHERE event_id=%s", (event.event_id,))

    assert ledger.commit_ingest(evidence, event)
    pending = ledger.pending()
    assert any(item.event_id == event.event_id for item in pending)
