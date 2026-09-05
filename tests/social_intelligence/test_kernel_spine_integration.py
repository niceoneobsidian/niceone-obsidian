from ois.domains.social_intelligence.connectors import ConnectorRegistry, GenericSocialConnector
from ois.domains.social_intelligence.runtime_registry import SocialCapabilityRegistry
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.registry import AgentRegistry, CapabilityRegistry, ToolRegistry


def test_m14_runs_through_authoritative_ois_spine() -> None:
    connectors = ConnectorRegistry()
    connectors.register(GenericSocialConnector("test-platform"))

    capabilities = CapabilityRegistry()
    agents = AgentRegistry()
    tools = ToolRegistry()
    social = SocialCapabilityRegistry(capabilities)
    counts = social.activate(agents, tools, connectors=connectors)

    assert counts["capabilities"] == 9
    spine = OISSpine(capabilities)
    result = spine.submit(SpineRequest(
        objective="build a content genome",
        capability_id="social.content.intelligence",
        capability_version="1.0.0",
        input={
            "content_id": "spine-content-1",
            "observations": [
                {"modality": "text", "features": {"hook": {"strength": 0.9}}},
            ],
        },
    ))

    assert result.status == "succeeded"
    assert result.output["content_genome"]["version"] == "m14.v1"
    assert any(event["type"] == "spine.verified" for event in result.evidence)
