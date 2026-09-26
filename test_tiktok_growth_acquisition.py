from uuid import uuid4

from ois.capabilities.tiktok_growth import (
    TikTokContentAgent,
    TikTokContentBrief,
    build_tiktok_plan,
)
from ois.kernel import ExecutionContext, ExecutionIdentity
from ois.kernel.contracts import InvocationRequest


def make_context() -> ExecutionContext:
    return ExecutionContext(
        identity=ExecutionIdentity(
            execution_id=uuid4(),
            tenant_id="ois-test",
        ),
        objective="Create a TikTok content plan",
    )


def test_plan_is_focused_and_limited():  # type: ignore
    plan = build_tiktok_plan(TikTokContentBrief(topic="TikTok SEO strategy"))
    assert plan.hook
    assert plan.caption
    assert len(plan.hashtags) <= 3
    assert "single_clear_topic" in plan.quality_checks
    assert "no_guaranteed_virality_claim" in plan.quality_checks


def test_agent_contract_is_stable():  # type: ignore
    agent = TikTokContentAgent()
    assert agent.contract.capability_id == "tiktok.content.plan"
    assert agent.contract.version == "1.0.0"
    assert agent.contract.idempotent is True


def test_empty_topic_is_rejected():  # type: ignore
    try:
        build_tiktok_plan(TikTokContentBrief(topic=""))
    except ValueError as exc:
        assert str(exc) == "topic is required"
    else:
        raise AssertionError("Expected ValueError")


def test_execution_provenance_is_not_reference_provenance():  # type: ignore
    result = TikTokContentAgent().invoke(
        InvocationRequest(
            invocation_id="tiktok-provenance-001",
            capability_id="tiktok.content.plan",
            input={"topic": "TikTok SEO"},
            execution=make_context(),
        )
    )

    assert result.status.value == "succeeded"
    assert "provenance" not in result.output
    assert result.metadata["execution_provenance"]["input_sha256"]
    assert result.metadata["execution_provenance"]["capability_version"] == "1.0.0"
