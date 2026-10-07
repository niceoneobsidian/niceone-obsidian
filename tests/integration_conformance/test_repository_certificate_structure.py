from __future__ import annotations

from ois.infrastructure.source_adapters import SourceAdapterRegistry, SportmonksFootballAdapter


def test_registered_sportmonks_adapter_has_structural_conformance_contract() -> None:
    registry = SourceAdapterRegistry()
    adapter = SportmonksFootballAdapter.register(registry)

    assert adapter.source_id == "sportmonks:football:v3"
    assert registry.list() == ("sportmonks:football:v3",)
    spec = registry.spec("sportmonks:football:v3")
    assert spec.provider == "sportmonks"
    assert spec.protocol == "rest"
    assert spec.capabilities == ("football.live", "football.fixtures", "evidence.raw")
    assert callable(adapter.ingest)
