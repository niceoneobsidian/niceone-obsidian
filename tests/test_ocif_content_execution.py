from __future__ import annotations

from ois.integration.ocif_content_execution import (
    OCIFContentExecutionCapability,
    authorize_ocif_content_request,
)
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.policy import DefaultPolicyEngine
from ois.registries import CapabilityRegistry


def request(mode: str = "sandbox_noop") -> SpineRequest:
    return SpineRequest(
        objective="Execute a reviewed content draft without publishing",
        capability_id="ocif.content.execute",
        capability_version="1.0.0",
        tenant_id="tenant-test",
        input={
            "approval_id": "approval-1",
            "draft_id": "draft-1",
            "content_sha256": "a" * 64,
            "draft_version": 1,
            "reviewer_id": "reviewer-1",
            "idempotency_key": "key-1",
            "mode": mode,
        },
    )


def test_ois_denial_blocks_ocif_content_execution() -> None:
    registry = CapabilityRegistry()
    registry.register(OCIFContentExecutionCapability())
    spine = OISSpine(registry, policy=DefaultPolicyEngine(allowed_permissions=()))
    result = spine.submit(request(), invocation_id="denied-content-run")
    assert result.status == "denied"
    assert result.output is None


def test_ois_allows_only_noop_for_approved_content() -> None:
    registry = CapabilityRegistry()
    registry.register(OCIFContentExecutionCapability())
    spine = OISSpine(
        registry,
        policy=DefaultPolicyEngine(allowed_permissions=("ocif.content.execute",)),
    )
    result = spine.submit(request(), invocation_id="approved-content-run")
    assert result.status == "succeeded"
    assert result.output["allowed"] is True
    assert result.output["external_side_effects"] is False


def test_ois_capability_rejects_live_publish_mode_even_when_permission_exists() -> None:
    registry = CapabilityRegistry()
    registry.register(OCIFContentExecutionCapability())
    spine = OISSpine(
        registry,
        policy=DefaultPolicyEngine(allowed_permissions=("ocif.content.execute",)),
    )
    result = spine.submit(request(mode="publish_live"), invocation_id="live-publish-denied")
    assert result.status == "failed"


def test_ocif_workflow_authorizer_calls_real_ois_spine() -> None:
    registry = CapabilityRegistry()
    registry.register(OCIFContentExecutionCapability())
    spine = OISSpine(
        registry,
        policy=DefaultPolicyEngine(allowed_permissions=("ocif.content.execute",)),
    )
    result = authorize_ocif_content_request(
        spine,
        {
            "approval_id": "approval-1",
            "draft_id": "draft-1",
            "content_sha256": "a" * 64,
            "draft_version": 1,
            "reviewer_id": "reviewer-1",
            "idempotency_key": "vertical-slice-key",
            "mode": "sandbox_noop",
        },
        tenant_id="tenant-test",
    )
    assert result["allowed"] is True
    assert result["invocation_id"] == "vertical-slice-key"
    assert result["external_side_effects"] is False
