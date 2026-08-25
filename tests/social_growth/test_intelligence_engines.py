from datetime import UTC, datetime

from ois.domains.social_growth.intelligence import (
    build_audience_profiles,
    build_competitor_profiles,
    cluster_topics,
    detect_trends,
    extract_creative_patterns,
    resolve_entities,
    validate_events,
)
from ois.domains.social_growth.schemas import Evidence, SocialEvent


def event(text: str, platform: str = "tiktok", entities: list[str] | None = None) -> SocialEvent:
    return SocialEvent(
        platform=platform,
        event_type="post",
        occurred_at=datetime.now(UTC),
        text=text,
        entities=entities or [],
        evidence=[Evidence(source_id="test")],
        metrics={"likes": 10, "impressions": 100},
    )


def test_quality_accepts_evidenced_events():
    report = validate_events([event("great launch")])
    assert report.accepted == 1
    assert report.rejected == 0


def test_entity_resolution_groups_normalized_labels():
    result = resolve_entities(
        [event("brand", entities=["Acme Brand"]), event("brand", entities=["Acme Brand"])]
    )
    assert result["acme brand"] == ("Acme Brand",)


def test_topic_clustering_returns_dominant_topic():
    result = cluster_topics([event("ai tools ai growth"), event("ai strategy")])
    assert result[0][0] == "ai"
    assert result[0][2] == 2


def test_trend_detection_returns_rising_signal():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    events = [
        SocialEvent(
            platform="x",
            event_type="post",
            occurred_at=base,
            text="alpha",
            evidence=[Evidence(source_id="test")],
        ),
        SocialEvent(
            platform="x",
            event_type="post",
            occurred_at=base.replace(hour=1),
            text="alpha alpha",
            evidence=[Evidence(source_id="test")],
        ),
    ]
    signals = detect_trends(events, min_velocity=0.1)
    assert any(s.value == "alpha" for s in signals)


def test_audience_profiles_group_by_platform():
    profiles = build_audience_profiles(
        [event("ai strategy", "tiktok"), event("ai tools", "tiktok"), event("seo", "youtube")]
    )
    assert {p.audience_id for p in profiles} == {"platform:tiktok", "platform:youtube"}


def test_competitor_profiles_compute_share_of_voice():
    profiles = build_competitor_profiles(
        [
            event("Acme launch", entities=["Acme"]),
            event("Acme update", entities=["Acme"]),
            event("Beta launch", entities=["Beta"]),
        ]
    )
    acme = next(p for p in profiles if p.name == "Acme")
    assert acme.share_of_voice == 2 / 3


def test_creative_patterns_extract_hooks():
    patterns = extract_creative_patterns([event("You won't believe this. Here is why.")])
    assert patterns[0].pattern_type == "hook"
    assert patterns[0].pattern == "You won't believe this"
