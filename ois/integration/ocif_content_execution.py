"""OIS capability boundary for approved OCIF content execution.

This capability authorizes only the sandbox/no-op execution mode. It deliberately
contains no social-platform publishing adapter.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries import CapabilityRegistry


class OCIFContentExecutionCapability:
    """Policy-gated execution receipt for a human-approved OCIF draft."""

    contract = CapabilityContract(
        capability_id="ocif.content.execute",
        version="1.0.0",
        description="Authorize a hash-bound approved OCIF draft in sandbox no-op mode.",
        input_schema={
            "type": "object",
            "required": [
                "approval_id", "draft_id", "content_sha256", "draft_version",
                "reviewer_id", "idempotency_key", "mode",
            ],
        },
        output_schema={"type": "object"},
        risk_level=RiskLevel.MEDIUM,
        permissions=("ocif.content.execute",),
        allowed_domains=("content_workflow",),
        timeout_seconds=15.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload: Mapping[str, Any] = request.input
        required = (
            "approval_id", "draft_id", "content_sha256", "draft_version",
            "reviewer_id", "idempotency_key",
        )
        missing = [key for key in required if not payload.get(key)]
        if missing:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "ValueError", "message": "missing fields: " + ", ".join(missing)},
            )
        if payload.get("mode") != "sandbox_noop":
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "PolicyError", "message": "only sandbox_noop mode is supported"},
            )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "allowed": True,
                "mode": "sandbox_noop",
                "external_side_effects": False,
                "approval_id": str(payload["approval_id"]),
                "draft_id": str(payload["draft_id"]),
                "content_sha256": str(payload["content_sha256"]),
                "draft_version": int(payload["draft_version"]),
                "idempotency_key": str(payload["idempotency_key"]),
            },
            metadata={"authorization_boundary": "ois", "capability_version": "1.0.0"},
        )


def register_ocif_content_execution_capability(
    registry: CapabilityRegistry,
) -> OCIFContentExecutionCapability:
    """Register the no-op capability in the OIS policy-governed registry."""
    capability = OCIFContentExecutionCapability()
    registry.register(capability)
    return capability
