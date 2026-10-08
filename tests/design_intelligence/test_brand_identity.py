from ois.design_intelligence.brand_identity import (
    BrandIdentityWorkflow,
    build_brand_identity_provider,
)
from ois.design_intelligence.fabric import DesignCapabilityFabric
from ois.design_intelligence.kernel_integration import register_design_kernel_capabilities
from ois.kernel.checkpoint import InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity


def test_brand_identity_workflow_produces_structured_design_system():
    r = BrandIdentityWorkflow().run(
        {
            "objective": "Create a differentiated intelligence brand",
            "audience": "strategic builders",
            "market": "AI systems",
            "category": "intelligence software",
            "differentiation_goal": "Make strategic intelligence visibly distinct",
            "brand_context": {
                "brand": "Obsidian",
                "category": "intelligence software",
                "audience": {"primary": "strategic builders"},
                "market": {"name": "AI systems"},
                "competitors": ("generic AI assistants",),
            },
        }
    )
    assert r["capability"] == "brand.identity"
    assert r["validation"].passed
    assert r["decision"].selected_direction
    assert r["artifacts"].brand_identity["positioning"]


def test_brand_identity_provider_executes_through_ois_kernel():
    p = build_brand_identity_provider()
    f = DesignCapabilityFabric()
    f.register_provider("brand.identity", p)
    reg = CapabilityRegistry()
    register_design_kernel_capabilities(reg, fabric=f)
    e = EvidenceLedger()
    rt = ExecutionRuntime(reg, InMemoryCheckpointStore(), e)
    c = ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="test", workflow_id="brand.identity", workflow_version="0.1"
        ),
        objective="Create a governed brand identity",
        intent={
            "audience": "builders",
            "market": "AI",
            "category": "software",
            "differentiation_goal": "strategic clarity",
            "brand_context": {
                "brand": "Example",
                "category": "software",
                "audience": {"primary": "builders"},
                "market": {"name": "AI"},
            },
        },
    )
    r = rt.execute(
        c,
        "brand.identity",
        "1.0.0",
        {"brief": "Create a differentiated identity"},
        invocation_id="brand-identity-provider-001",
    )
    assert r.status.value == "succeeded"
    assert r.output["output"]["artifact_type"] == "brand_identity_system"
    assert any(x.event_type == "capability.completed" for x in e.list(c.identity.execution_id))


def test_provider_does_not_own_ois_governance():
    p = build_brand_identity_provider()
    assert not hasattr(p, "authorize")
    assert not hasattr(p, "checkpoint")
    assert not hasattr(p, "set_production_state")
