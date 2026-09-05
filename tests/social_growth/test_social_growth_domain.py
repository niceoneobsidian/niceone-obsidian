import datetime

from ois.domains.social_growth.algorithms import (
    engagement_rate,
    sentiment_score,
    signals_from_events,
    topic_counts,
)
from ois.domains.social_growth.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_growth.schemas import PublishIntent, SocialEvent
from ois.domains.social_growth.workflows import (
    CONTENT_PUBLISH_WORKFLOW,
    RESEARCH_WORKFLOW,
    build_research_brief,
)


def event(text: str, **metrics) -> SocialEvent:
    return SocialEvent(
        platform="tiktok",
        event_type="post",
        occurred_at=datetime.datetime.now(datetime.UTC),
        text=text,
        metrics=metrics,
    )


def test_sentiment_and_topics_are_deterministic():
    assert sentiment_score("great amazing") > 0
    assert topic_counts([event("python python ai")])[0] == ("python", 2)


def test_engagement_rate():
    assert engagement_rate(event("hello", likes=10, comments=5, impressions=100)) == 0.15


def test_signal_generation():
    signals = signals_from_events([event("great ai")])
    assert any(s.signal_type == "sentiment" for s in signals)
    assert any(s.signal_type == "topic" for s in signals)


def test_research_brief():
    brief = build_research_brief("ai trends", [event("great ai")])
    assert brief.query == "ai trends"
    assert brief.signals


def test_connector_registry_and_validation():
    connector = GenericSocialConnector("tiktok")
    registry = ConnectorRegistry()
    registry.register(connector)
    assert registry.platforms() == ("tiktok",)
    intent = PublishIntent(platform="tiktok", account_ref="acct", content={"text": "hello"})
    assert connector.validate_publish(intent) == []


def test_workflows_are_versioned_and_side_effects_are_explicit():
    assert RESEARCH_WORKFLOW.version == 1
    assert CONTENT_PUBLISH_WORKFLOW.version == 1
    publish = CONTENT_PUBLISH_WORKFLOW.steps[-3]
    assert publish.requires_approval is True
    assert CONTENT_PUBLISH_WORKFLOW.steps[-2].requires_approval is True
