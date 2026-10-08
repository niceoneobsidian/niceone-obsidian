"""Bind Design Intelligence capabilities to the canonical OIS Kernel.

The design domain owns design semantics and provider routing. OIS owns the
CapabilityContract, policy, validation, execution, checkpointing, idempotency,
recovery, and evidence lifecycle.
"""

from __future__ import annotations

from typing import Any

from ois.design_intelligence.catalog import DESIGN_CAPABILITIES, DesignCapability
from ois.design_intelligence.fabric import DesignCapabilityFabric
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel


_RISK_LEVELS = {
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
    "critical": RiskLevel.CRITICAL,
}


class KernelDesignCapability:
    """Expose one design-domain capability through the OIS execution contract."""

    def __init__(
        self,
        capability: DesignCapability,
        fabric: DesignCapabilityFabric,
    ) -> None:
        self.capability = capability
        self.fabric = fabric
        self._contract = CapabilityContract(
            capability_id=capability.id,
            version="1.0.0",
            description=capability.description,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level=_RISK_LEVELS.get(capability.risk_class, RiskLevel.MEDIUM),
            allowed_domains=("design_intelligence", capability.family),
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    @property
    def contract(self) -> CapabilityContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        request.execution.working_memory["brand.identity.input"] = dict(request.input)
        result = self.fabric.execute(self.capability.id, request.execution)
        if result.status == "unbound":
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": "DesignProviderUnavailable",
                    "message": (
                        f"No provider is bound for design capability "
                        f"{self.contract.capability_id}."
                    ),
                    "failure_class": "tool",
                    "capability_status": "unbound",
                },
                metadata={
                    "domain": "design_intelligence",
                    "validation": tuple(result.validation or ()),
                    "evidence": tuple(result.evidence or ()),
                },
            )

        output: dict[str, Any] = {
            "capability": self.contract.capability_id,
            "status": result.status,
            "output": result.output,
            "validation": tuple(result.validation or ()),
            "evidence": tuple(result.evidence or ()),
        }
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
            metadata={"domain": "design_intelligence"},
        )


def register_design_kernel_capabilities(
    registry: CapabilityRegistry,
    *,
    fabric: DesignCapabilityFabric | None = None,
) -> DesignCapabilityFabric:
    """Register the canonical design capability catalog in the OIS Kernel registry.

    Provider binding remains explicit: registration makes the capabilities
    routable and governable, while execution only succeeds for capabilities
    whose design provider has been bound to the shared fabric.
    """
    design_fabric = fabric or DesignCapabilityFabric()
    for capability in DESIGN_CAPABILITIES:
        registry.register(KernelDesignCapability(capability, design_fabric))
    return design_fabric


__all__ = ["KernelDesignCapability", "register_design_kernel_capabilities"]
