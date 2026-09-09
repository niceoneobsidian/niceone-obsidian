"""OIS-governed social publishing capability."""

from __future__ import annotations

from collections.abc import Mapping

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .connectors import ConnectorRegistry
from .schemas import PublishIntent


class SocialPublishCapability:
    """External publishing is exposed only as a kernel capability."""

    contract = CapabilityContract(
        capability_id="social.publish",
        version="1.0.0",
        description=(
            "Publish an approved social content intent through a registered platform connector."
        ),
        input_schema={"type": "object", "required": ["intent"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.HIGH,
        permissions=("social.publish",),
        allowed_domains=("social_growth",),
        timeout_seconds=60.0,
        max_retries=0,
        side_effects=SideEffectLevel.IRREVERSIBLE,
        idempotent=False,
    )

    def __init__(self, connectors: ConnectorRegistry) -> None:
        self._connectors = connectors

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        try:
            raw = request.input.get("intent")
            if not isinstance(raw, Mapping):
                raise ValueError("intent must be an object")
            intent = PublishIntent.model_validate(raw)
            if not intent.requires_approval:
                raise ValueError("publish intent must require approval")
            approved = any(
                str(item.get("intent_id")) == intent.intent_id and bool(item.get("approved"))
                for item in request.execution.approvals
                if isinstance(item, Mapping)
            )
            if not approved:
                raise PermissionError("publish intent has no matching approval")
            connector = self._connectors.get(intent.platform)
            result = connector.publish(intent)
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.SUCCEEDED,
                output=result,
                metadata={"platform": intent.platform, "intent_id": intent.intent_id},
            )
        except (KeyError, ValueError, RuntimeError, PermissionError) as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
