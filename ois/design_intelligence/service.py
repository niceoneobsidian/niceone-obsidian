"""Design capability fabric service."""

from dataclasses import dataclass
from typing import Any

from ois.design_intelligence.adapters import AdapterRegistry, AdapterRequest, AdapterResponse
from ois.design_intelligence.blueprints import FAMILIES, SUBCAPABILITIES, WORKFLOWS, validate_catalog


@dataclass(frozen=True)
class CapabilityPlan:
    family: str
    sub_capability: str
    workflow: str
    skills: tuple[str, ...]
    validators: tuple[str, ...]
    evidence: tuple[str, ...]
    adapters: tuple[str, ...]


class DesignCapabilityService:
    """Resolves a design request into an executable, governable capability plan."""

    def __init__(self, adapters: AdapterRegistry | None = None) -> None:
        self.adapters = adapters or AdapterRegistry()

    def plan(self, family_id: str, sub_capability_id: str, workflow_id: str) -> CapabilityPlan:
        family = FAMILIES[family_id]
        sub = SUBCAPABILITIES[sub_capability_id]
        wf = WORKFLOWS[workflow_id]
        if sub_capability_id not in family.sub_capabilities:
            raise ValueError(f"{sub_capability_id} is not part of {family_id}")
        if workflow_id not in sub.workflows:
            raise ValueError(f"{workflow_id} is not part of {sub_capability_id}")
        return CapabilityPlan(
            family.id, sub.id, wf.id, sub.skills, sub.validators, sub.evidence, sub.adapters
        )

    def execute(
        self,
        plan: CapabilityPlan,
        inputs: dict[str, Any],
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        results: list[AdapterResponse] = []
        for adapter_id in plan.adapters:
            adapter = self.adapters.resolve(adapter_id)
            request = AdapterRequest(
                plan.sub_capability,
                plan.workflow,
                inputs,
                constraints or {},
            )
            if hasattr(adapter, "generate"):
                response = adapter.generate(request)
            elif hasattr(adapter, "render"):
                response = adapter.render(request)
            elif hasattr(adapter, "inspect"):
                response = adapter.inspect(request)
            elif hasattr(adapter, "preflight"):
                response = adapter.preflight(request)
            else:
                raise TypeError(f"Adapter {adapter_id} exposes no supported operation")
            results.append(response)
        return {
            "status": "executed",
            "capability": plan.sub_capability,
            "workflow": plan.workflow,
            "results": results,
            "validators": plan.validators,
            "evidence": plan.evidence,
        }

    @staticmethod
    def validate() -> list[str]:
        return validate_catalog()
