from dataclasses import dataclass
import pytest
from ois.infrastructure.source_adapters.base import SourceAdapterRegistry
from ois.infrastructure.source_gateway.contracts import SourceSpec
from ois.integration_conformance import CONFORMANCE_COLUMNS, IntegrationConformance, audit_registered_integrations

@dataclass
class Adapter:
    source_id: str = "github:repo"
    def ingest(self, **_kwargs: object) -> object: return object()

def test_discovers_registered_sources_and_emits_exact_23_columns() -> None:
    registry = SourceAdapterRegistry()
    registry.register(Adapter(), SourceSpec("github:repo", "github", "http", capabilities=("read_repository",)))
    report = IntegrationConformance(registry).audit()
    assert report.columns == CONFORMANCE_COLUMNS
    assert len(CONFORMANCE_COLUMNS) == 23
    assert report.matrix[0]["PROVIDER"] == "IMPLEMENTED"
    assert report.matrix[0]["ADAPTER"] == "IMPLEMENTED"
    assert report.matrix[0]["REGISTRATION"] == "IMPLEMENTED"
    assert report.matrix[0]["CAPABILITY"] == "IMPLEMENTED"
    assert report.matrix[0]["PRODUCTION VERIFICATION"] == "UNKNOWN"

def test_discovery_is_registry_driven_and_sorted() -> None:
    registry = SourceAdapterRegistry()
    registry.register(Adapter("zeta:source"), SourceSpec("zeta:source", "zeta", "http"))
    registry.register(Adapter("alpha:source"), SourceSpec("alpha:source", "alpha", "http"))
    assert IntegrationConformance(registry).discover() == ("alpha:source", "zeta:source")

def test_unknown_is_not_promoted_by_inference() -> None:
    registry = SourceAdapterRegistry()
    registry.register(Adapter(), SourceSpec("github:repo", "github", "http"))
    row = audit_registered_integrations(registry).matrix[0]
    assert row["LIVE TEST"] == "UNKNOWN"
    assert row["E2E TEST"] == "UNKNOWN"
    assert row["PRODUCTION VERIFICATION"] == "UNKNOWN"

def test_explicit_verifier_evidence_overrides_unknown() -> None:
    registry = SourceAdapterRegistry()
    registry.register(Adapter(), SourceSpec("github:repo", "github", "http"))
    def verify(_source_id, _adapter, _spec):
        return {"AUTH": "IMPLEMENTED", "STRUCTURAL TEST": {"status": "TESTED", "evidence": ["test"]}, "CONTRACT TEST": "TESTED"}
    row = IntegrationConformance(registry, verifier=verify).audit().matrix[0]
    assert row["AUTH"] == "IMPLEMENTED"
    assert row["STRUCTURAL TEST"] == "TESTED"
    assert row["CONTRACT TEST"] == "TESTED"

def test_unknown_column_override_is_rejected() -> None:
    registry = SourceAdapterRegistry()
    registry.register(Adapter(), SourceSpec("github:repo", "github", "http"))
    def verify(_source_id, _adapter, _spec): return {"NOT A COLUMN": "TESTED"}
    with pytest.raises(ValueError, match="unknown conformance column"): IntegrationConformance(registry, verifier=verify).audit()