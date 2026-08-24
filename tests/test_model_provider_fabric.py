import pytest

from ois.models import (
    DeterministicTestProvider,
    LLMGateway,
    ModelRegistry,
    ModelRequest,
    ModelRoute,
)


def gateway() -> LLMGateway:
    registry = ModelRegistry()
    registry.register(
        ModelRoute(
            route_id="test.public.v1",
            provider_id=DeterministicTestProvider.provider_id,
            model_id="deterministic-test",
            version="1.0.0",
            capabilities=frozenset({"text", "structured_output"}),
            max_input_classification="public",
            risk_levels=frozenset({"low"}),
            priority=1,
        ),
        DeterministicTestProvider(),
    )
    return LLMGateway(registry)


def test_gateway_selects_registered_provider_and_preserves_provenance() -> None:
    response = gateway().invoke(
        ModelRequest(
            capability_id="tiktok.content.plan",
            input={"topic": "AI agents"},
            required_capabilities=frozenset({"text", "structured_output"}),
        )
    )

    assert response.route.provider_id == "deterministic.test"
    assert response.route.model_id == "deterministic-test"
    assert response.route.version == "1.0.0"
    assert response.metadata["provider_mode"] == "deterministic_test"


def test_router_rejects_ineligible_data_classification() -> None:
    with pytest.raises(LookupError, match="no eligible model route"):
        gateway().invoke(
            ModelRequest(
                capability_id="tiktok.content.plan",
                input={"topic": "restricted subject"},
                data_classification="restricted",
            )
        )


def test_router_rejects_missing_model_capability() -> None:
    with pytest.raises(LookupError, match="no eligible model route"):
        gateway().invoke(
            ModelRequest(
                capability_id="tiktok.content.plan",
                input={"topic": "AI agents"},
                required_capabilities=frozenset({"vision"}),
            )
        )
