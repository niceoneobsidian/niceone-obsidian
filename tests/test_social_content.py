from ois.domains.social_content.contracts import ContentObjective, ContentObjectiveRequest, Platform
from ois.domains.social_content.creative import CreativeProvider
from ois.domains.social_content.research import ResearchProvider
from ois.domains.social_content.workflow import SocialContentWorkflow


def _workflow(results):
    research = ResearchProvider(lambda _: results)
    creative = CreativeProvider(
        lambda _: {
            "hook": "Stop scrolling: here is the useful part.",
            "body": "A concise, platform-native explanation.",
            "cta": "Save this for later.",
            "keywords": ["AI agents"],
            "hashtags": ["#AI"],
            "visual_prompts": ["Clean editorial technology visual"],
        }
    )
    return SocialContentWorkflow(research, creative)


def test_fresh_research_requires_evidence_and_validates_package():
    workflow = _workflow(
        [
            {
                "source_id": "SRC-1",
                "title": "Primary source",
                "url": "https://example.com/source",
                "verification": "verified",
            }
        ]
    )
    request = ContentObjectiveRequest(
        topic="AI agents",
        platforms=[Platform.TIKTOK, Platform.INSTAGRAM],
        audience="business owners",
        objective=ContentObjective.EDUCATION,
        freshness_required=True,
        citation_required=True,
    )

    result = workflow.run(request)

    assert result.publishable is True
    assert result.review_status == "validated"
    assert len(result.variants) == 2
    assert all(v.evidence for v in result.variants)


def test_empty_required_research_blocks_generation_for_publish():
    workflow = _workflow([])
    request = ContentObjectiveRequest(
        topic="latest platform changes",
        platforms=[Platform.X],
        freshness_required=True,
        citation_required=True,
    )

    result = workflow.run(request)

    assert result.publishable is False
    assert result.review_status == "rejected"
    assert "research_insufficient" in result.review_feedback


def test_connector_never_publishes_without_authorization():
    from ois.domains.social_content.connectors import (
        AuthorizationRequiredError,
        ConnectorSpec,
        SafeConnector,
    )

    connector = SafeConnector(ConnectorSpec(Platform.TIKTOK, "TikTok Content Posting API", "official_api"))
    variant = _workflow([]).creative.generate(
        ContentObjectiveRequest(topic="x", platforms=[Platform.TIKTOK]),
        Platform.TIKTOK,
        [],
    )

    try:
        connector.publish(variant, authorized=False)
    except AuthorizationRequiredError:
        pass
    else:
        raise AssertionError("unauthorized publishing must be blocked")
