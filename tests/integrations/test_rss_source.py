from datetime import UTC, datetime

from ois.infrastructure.source_gateway import (
    SQLiteRawEvidenceWriter,
    SQLiteSourceLedger,
    SourceGateway,
    SQLiteOutboxStore,
)
from ois.integrations.rss.source import RSSSource, RSSItem


def test_rss_item_preserves_source_identity() -> None:
    item = RSSItem(
        "id-1",
        "AI agents",
        "https://example.test/1",
        datetime(2026, 9, 22, tzinfo=UTC),
        "description",
    )
    payload = item.as_payload()
    assert payload["id"] == "id-1"
    assert payload["title"] == "AI agents"
    assert payload["uri"] == "https://example.test/1"


def test_rss_source_commits_items_through_gateway(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b"""<?xml version="1.0"?><rss><channel>
            <item><guid>1</guid><title>AI agents</title>
            <link>https://example.test/1</link></item>
            </channel></rss>"""

    monkeypatch.setattr(
        "ois.integrations.rss.source.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    evidence = SQLiteRawEvidenceWriter()
    outbox = SQLiteOutboxStore()
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=evidence, outbox=outbox)
    source = RSSSource(feed_url="https://example.test/rss", gateway=gateway)

    run = source.fetch(tenant_id="tenant", workspace_id="workspace")
    assert run.items == 1
    assert len(run.evidence_ids) == 1
    assert len(run.event_ids) == 1
    assert len(outbox.pending()) == 1
