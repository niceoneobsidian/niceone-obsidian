from ois.design_intelligence import DesignCapabilityService
from ois.design_intelligence.blueprints import validate_catalog
from ois.design_intelligence.catalog import DESIGN_CAPABILITIES
from ois.design_intelligence.fabric import DesignCapabilityFabric
from ois.kernel.state import ExecutionContext, ExecutionIdentity


def test_design_domain_is_native_to_ois() -> None:
    assert len(DESIGN_CAPABILITIES) == 17
    assert validate_catalog() == []
    service = DesignCapabilityService()
    plan = service.plan("brand_identity", "brand.strategy", "brand.strategy.develop")
    assert plan.family == "brand_identity"
    assert plan.sub_capability == "brand.strategy"


def test_design_fabric_uses_ois_execution_context() -> None:
    context = ExecutionContext(
        identity=ExecutionIdentity(),
        objective="Create a governed brand identity",
    )
    fabric = DesignCapabilityFabric()
    result = fabric.execute("brand.identity", context)
    assert result.status == "unbound"
    assert result.capability_id == "brand.identity"
    assert result.evidence
    assert result.validation
