from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel import (
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)
from ois.registries import CapabilityRegistry


class EchoCapability:
    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="test.echo",
            version="1.0.0",
            description="P0 golden-path capability",
            risk_level=RiskLevel.LOW,
            side_effects=SideEffectLevel.NONE,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"echo": dict(request.input)},
        )


def test_real_control_plane_to_kernel_vertical_path() -> None:
    registry = CapabilityRegistry()
    registry.register("test.echo", "1.0.0", EchoCapability())

    spine = OISSpine(registry)
    result = spine.submit(
        SpineRequest(
            objective="prove the governed vertical path",
            capability_id="test.echo",
            capability_version="1.0.0",
            input={"value": "golden-path"},
            tenant_id="tenant-e2e",
        )
    )

    assert result.status == "succeeded"
    assert result.output == {"echo": {"value": "golden-path"}}
    assert any(event["event_type"] == "spine.intent.accepted" for event in result.evidence)
    assert any(event["event_type"] == "spine.verified" for event in result.evidence)


def test_vertical_path_rejects_unknown_capability_without_execution() -> None:
    spine = OISSpine(CapabilityRegistry())

    try:
        spine.submit(
            SpineRequest(
                objective="must not execute",
                capability_id="missing.capability",
                capability_version="1.0.0",
            )
        )
    except KeyError:
        pass
    else:
        raise AssertionError("unknown capabilities must not cross the execution boundary")
