from ois.capabilities.tiktok_growth import (
    ACQUISITION_SOURCES,
    TikTokContentAgent,
    TikTokContentBrief,
    build_tiktok_plan,
)


def test_acquisition_sources_preserve_legal_boundary():
    sources = {source["id"]: source for source in ACQUISITION_SOURCES}
    assert sources["tiktok-viral-hooks"]["commercial_corpus_use"] is False
    assert sources["captionaize"]["license"] == "MIT"
    assert sources["social-media-caption-generator-claude"]["license"] == "MIT"


def test_plan_is_focused_and_limited():
    plan = build_tiktok_plan(
        TikTokContentBrief(topic="TikTok SEO strategy", source_text="how to improve search")
    )
    assert plan.hook
    assert plan.caption
    assert len(plan.hashtags) <= 3
    assert "single_clear_topic" in plan.quality_checks
    assert "no_claim_of_guaranteed_virality" in plan.quality_checks


def test_agent_contract_is_stable():
    agent = TikTokContentAgent()
    assert agent.contract.capability_id == "tiktok.content.plan"
    assert agent.contract.version == "1.0.0"
    assert agent.contract.idempotent is True


def test_empty_topic_is_rejected():
    try:
        build_tiktok_plan(TikTokContentBrief(topic=""))
    except ValueError as exc:
        assert str(exc) == "topic is required"
    else:
        raise AssertionError("Expected ValueError")
