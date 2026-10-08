"""Reference brand.identity provider executed through the OIS fabric."""

from __future__ import annotations

from typing import Any

from ois.design_intelligence.catalog import DesignCapability
from ois.kernel.state import ExecutionContext

from .workflow import BrandIdentityWorkflow


class BrandIdentityProvider:
    provider_id = "brand.identity.native"
    version = "0.1.0"

    def __init__(self, workflow: BrandIdentityWorkflow | None = None) -> None:
        self.workflow = workflow or BrandIdentityWorkflow()

    def execute(self, capability: DesignCapability, context: ExecutionContext) -> dict[str, Any]:
        if capability.id != "brand.identity":
            raise ValueError(f"Unsupported capability: {capability.id}")
        payload = dict(context.intent or {})
        payload.update(context.working_memory.get("brand.identity.input", {}))
        payload.setdefault("objective", context.objective)
        return {
            "artifact_type": "brand_identity_system",
            "provider_id": self.provider_id,
            "provider_version": self.version,
            "output": self.workflow.run(payload),
        }


def build_brand_identity_provider() -> BrandIdentityProvider:
    return BrandIdentityProvider()
