from ois.domains.social_intelligence.inventory import INVENTORY


def test_social_intelligence_inventory_has_394_structures() -> None:
    assert len(INVENTORY) == 394


def test_inventory_uses_existing_ois_registries() -> None:
    allowed = {
        "capability_registry",
        "agent_registry",
        "tool_registry",
        "workflow_registry",
        "model_registry",
        "policy",
        "validation",
        "memory",
        "measurement",
        "learning",
        "recovery",
        "observability",
    }
    assert {entry["target_registry"] for entry in INVENTORY} <= allowed


def test_inventory_entries_are_versionable_registry_objects() -> None:
    assert all(entry["id"] and entry["name"] for entry in INVENTORY)
    assert all(entry["integration_mode"] == "extend_existing_contract" for entry in INVENTORY)
