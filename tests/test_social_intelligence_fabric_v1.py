from ois.domains.social_intelligence.analytics import normalize_platform_metrics, summarize_metrics
from ois.domains.social_intelligence.fabric import InMemorySocialEventStore, SocialSourceRegistry, build_signals, detect_trends, normalize_events
from ois.domains.social_intelligence.platforms import default_platform_registry
from ois.domains.social_intelligence.sources import PayloadSource, collect_source


def test_platform_registry_contains_reference_channels() -> None:
    registry = default_platform_registry()
    ids = {spec.platform_id for spec in registry.list()}
    assert {"bluesky", "mastodon", "tiktok", "instagram", "youtube", "linkedin"} <= ids


def test_ingest_is_deduplicated_and_signals_are_evidence_linked() -> None:
    payloads = [
        {"id": "1", "event_type": "post", "text": "one", "topics": ["ai"], "engagement": {"likes": 10}},
        {"id": "2", "event_type": "post", "text": "two", "topics": ["ai"], "engagement": {"likes": 20}},
    ]
    events = normalize_events("bluesky", payloads)
    store = InMemorySocialEventStore()
    assert sum(store.append(event) for event in events) == 2
    assert store.append(events[0]) is False

    signals = build_signals(store.list())
    trends = detect_trends(store.list())
    assert signals[0].value == "ai"
    assert signals[0].source_event_ids == ("bluesky:1", "bluesky:2")
    assert trends[0].topic == "ai"


def test_source_registry_normalizes_collected_payloads() -> None:
    registry = SocialSourceRegistry()
    registry.register(PayloadSource("reddit", [{"id": "r1", "topics": ["python"]}]))
    batch = collect_source(registry, "reddit")
    assert batch.events[0].event_id == "reddit:r1"
    assert batch.events[0].evidence


def test_metrics_normalize_without_fabricating_missing_fields() -> None:
    metric = normalize_platform_metrics("tiktok", "c1", "2026-09-10T00:00:00Z", {"views": 100, "likes": "unknown"}, "test")
    assert metric.metrics == {"views": 100.0}
    summary = summarize_metrics([metric])
    assert summary.totals == {"views": 100.0}
    assert summary.averages == {"views": 100.0}
