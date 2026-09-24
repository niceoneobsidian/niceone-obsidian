from __future__ import annotations

from datetime import UTC, datetime

from ois.domains.social_intelligence.postgres_store import PostgresSocialSliceStore
from ois.domains.social_intelligence.schemas import SocialPost
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
