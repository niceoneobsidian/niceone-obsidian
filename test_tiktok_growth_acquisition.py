from ois.capabilities.tiktok_growth import (
    TikTokContentAgent,
    TikTokContentBrief,
    build_tiktok_plan,
)


def test_plan_is_focused_and_limited():
    plan = build_tiktok_plan(TikTokContentBrief(topic="TikTok SEO strategy"))
    assert plan.hook
    assert plan.caption
    assert len(plan.hashtags) <= 3
    assert "single_clear_topic" in plan.quality_checks
    assert "no_guaranteed_virality_claim" in plan.quality_checks


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


def test_execution_provenance_is_not_reference_provenance():
    from ois.kernel.contracts import InvocationRequest

    result = TikTokContentAgent().invoke(
        InvocationRequest(
            invocation_id="tiktok-provenance-001",
            capability_id="tiktok.content.plan",
            input={"topic": "TikTok SEO"},
        )
    )

    assert result.status.value == "succeeded"
    assert "provenance" not in result.output
    assert result.metadata["execution_provenance"]["input_sha256"]
    assert result.metadata["execution_provenance"]["capability_version"] == "1.0.0"
