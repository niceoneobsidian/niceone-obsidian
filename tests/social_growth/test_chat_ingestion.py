from datetime import UTC, datetime

from ois.domains.social_growth.analytics_store import SQLiteAnalyticsStore
from ois.domains.social_growth.chat_ingestion import ChatObservation, ingest_chat_observations, normalize_observation
from ois.domains.social_growth.persistence import SQLiteSocialEventStore


def test_chat_observation_normalizes_with_provenance_and_stable_id():
    observed_at = datetime(2026, 9, 13, 15, 0, tzinfo=UTC)
    observation = ChatObservation(
        platform="tiktok",
        event_type="content_observation",
        occurred_at=observed_at,
        text="Hook: stop scrolling if you want better retention",
        metrics={"views": 1200, "likes": 96, "engagement_rate": 0.08},
        entities=("retention",),
        source_uri="chat://current-session/tiktok/001",
    )

    first = normalize_observation(observation)
    second = normalize_observation(observation)

    assert first.external_id == second.external_id
    assert first.external_id.startswith("chatgpt:")
    assert first.platform == "tiktok"
    assert first.evidence[0].source_id == "chatgpt"
    assert first.evidence[0].uri == observation.source_uri
    assert first.metrics["views"] == 1200


def test_chat_ingestion_deduplicates_and_materializes_metrics():
    observed_at = datetime(2026, 9, 13, 15, 0, tzinfo=UTC)
    observation = ChatObservation(
        platform="instagram",
        event_type="content_observation",
        occurred_at=observed_at,
        text="A practical hook",
        external_id="ig:post:123",
        metrics={"views": 500, "likes": 40},
        source_uri="chat://current-session/instagram/123",
    )
    events_store = SQLiteSocialEventStore()
    analytics_store = SQLiteAnalyticsStore()

    events, added, metrics_added = ingest_chat_observations(
        [observation, observation], events_store, analytics_store
    )

    assert len(events) == 2
    assert added == 1
    assert metrics_added == 2
    assert len(events_store.list(platform="instagram")) == 1
    assert analytics_store.latest("ig:post:123", "views").value == 500
