"""Design Intelligence entry point into the canonical OIS execution spine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ois.design_intelligence.fabric import DesignCapabilityFabric
from ois.design_intelligence.kernel_integration import register_design_kernel_capabilities
from ois.integration.spine import OISSpine, SpineRequest, SpineResult
from ois.registries import CapabilityRegistry


@dataclass
class DesignOISRuntime:
    """Governed Design Intelligence runtime backed by the OIS spine."""

    registry: CapabilityRegistry
    fabric: DesignCapabilityFabric
    spine: OISSpine

    @classmethod
    def create(cls) -> DesignOISRuntime:
        registry = CapabilityRegistry()
        fabric = register_design_kernel_capabilities(registry)
        spine = OISSpine(registry)
        return cls(registry=registry, fabric=fabric, spine=spine)

    def submit(
        self,
        *,
        objective: str,
        capability_id: str,
        capability_version: str = "1.0.0",
        input_data: dict[str, Any] | None = None,
        tenant_id: str = "default",
        workflow_id: str = "design_intelligence",
        workflow_version: str = "1.0",
        invocation_id: str | None = None,
    ) -> SpineResult:
        return self.spine.submit(
            SpineRequest(
                objective=objective,
                capability_id=capability_id,
                capability_version=capability_version,
                input=input_data or {},
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
            ),
            invocation_id=invocation_id,
        )


__all__ = ["DesignOISRuntime"]
