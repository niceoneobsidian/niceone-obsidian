from datetime import UTC, datetime, timedelta

from ois.domains.social_growth.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_growth.persistence import SQLiteSocialEventStore
from ois.domains.social_intelligence.ingestion import IngestionPipeline
from ois.domains.social_intelligence.source import (
    SocialSource,
    SourceRegistry,
    SourceStatus,
)
from ois.domains.social_intelligence.store import SQLiteIntelligenceStore


def test_g1_ingestion_persists_events_and_research_brief() -> None:
    connectors = ConnectorRegistry()
    connectors.register(GenericSocialConnector("tiktok"))
    sources = SourceRegistry()
    sources.register(SocialSource(source_id="tiktok:test", platform="tiktok"))

    events = SQLiteSocialEventStore()
    intelligence = SQLiteIntelligenceStore()
    pipeline = IngestionPipeline(
        connectors=connectors,
        sources=sources,
        event_store=events,
        intelligence_store=intelligence,
    )

    report = pipeline.ingest(
        "tiktok:test",
        [
            {
                "id": "post-1",
                "event_type": "post",
                "occurred_at": "2026-09-21T10:00:00+00:00",
                "text": "AI agents are changing creative workflows",
                "entities": ["AI"],
            }
        ],
        research_query="AI agent social intelligence",
    )

    assert report.accepted == 1
    assert report.research_brief_id is not None
    assert report.research_brief is not None
    assert (
        intelligence.list_research_briefs(limit=1)[0].query
        == "AI agent social intelligence"
    )
    assert sources.status("tiktok:test") == SourceStatus.HEALTHY


def test_g1_source_health_becomes_stale() -> None:
    registry = SourceRegistry()
    registry.register(
        SocialSource(source_id="x:test", platform="x", stale_after_seconds=60)
    )
    observed = datetime.now(UTC) - timedelta(minutes=2)
    registry.record_health("x:test", events_ingested=1, observed_at=observed)
    assert registry.status("x:test") == SourceStatus.STALE
