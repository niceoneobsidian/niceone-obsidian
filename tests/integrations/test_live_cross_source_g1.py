"""Opt-in G1 acceptance test against two external production sources."""
import os
from urllib.parse import quote

import pytest

from ois.domains.social_intelligence.graph import SQLiteEvidenceGraph
from ois.domains.social_intelligence.pipeline import G1ResearchPipeline
from ois.infrastructure.source_gateway import SQLiteSourceLedger, SourceGateway
from ois.integrations.rss.source import RSSSource
from ois.integrations.tiktok.client import TikTokDisplayClient
from ois.integrations.tiktok.source import TikTokSource


@pytest.mark.integration
def test_live_cross_source_g1_acceptance() -> None:
    """Require authorized TikTok data plus a live RSS query for one topic.

    Required environment:
      OIS_TIKTOK_ACCESS_TOKEN
      OIS_G1_CROSS_SOURCE_TOPIC
      OIS_G1_RSS_URL (defaults to a Google News RSS search URL)
    """
    token = os.getenv("OIS_TIKTOK_ACCESS_TOKEN")
    topic = os.getenv("OIS_G1_CROSS_SOURCE_TOPIC")
    if not token or not topic:
        pytest.skip(
            "OIS_TIKTOK_ACCESS_TOKEN and OIS_G1_CROSS_SOURCE_TOPIC are required"
        )

    rss_url = os.getenv(
        "OIS_G1_RSS_URL",
        "https://news.google.com/rss/search?q="
        + quote(topic)
        + "&hl=en-US&gl=US&ceid=US:en",
    )

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=ledger, outbox=ledger)
    cursor: list[str | None] = [None]
    tiktok = TikTokSource(
        client=TikTokDisplayClient(token),
        gateway=gateway,
        get_cursor=lambda: cursor[0],
        advance_cursor=lambda value: cursor.__setitem__(0, value),
    )
    rss = RSSSource(feed_url=rss_url, gateway=gateway)

    tiktok_result = tiktok.ingest_pages(
        tenant_id="live-g1",
        workspace_id="live-g1",
        credential_id="external",
        max_pages=1,
    )
    assert tiktok_result.evidence_ids

    rss_result = rss.fetch(
        tenant_id="live-g1",
        workspace_id="live-g1",
        max_items=10,
        topic=topic,
    )
    assert rss_result.evidence_ids

    graph = SQLiteEvidenceGraph()
    pipeline = G1ResearchPipeline(
        outbox=ledger,
        graph=graph,
        evidence_reader=ledger,
    )
    pipeline.project_pending(limit=100)

    brief = pipeline.research(
        query=topic,
        tenant_id="live-g1",
        workspace_id="live-g1",
        entity_names=[topic],
    )

    sources = {source.source_id for source in brief.sources}
    assert "tiktok.display.v2" in sources
    assert "rss.news" in sources
    assert brief.confidence >= 0.65
    assert not ledger.pending()
