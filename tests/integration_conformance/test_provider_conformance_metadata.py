import pytest

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry
from ois.infrastructure.source_gateway.contracts import SourceSpec
from ois.integration.conformance import IntegrationConformance
from ois.integration.conformance_metadata import (
    ConformanceEvidence,
    ProviderConformanceMetadata,
)


class Adapter:
    source_id = "example.api.v1"

    def ingest(self, **_kwargs: object) -> object:
        return object()


def test_provider_metadata_is_bound_to_registered_source() -> None:
    registry = SourceAdapterRegistry()
    metadata = ProviderConformanceMetadata(
        source_id="example.api.v1",
        claims={
            "AUTH": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/example.py",),
                "Explicit authentication binding.",
            ),
            "TIMEOUT": ConformanceEvidence(
                "IMPLEMENTED",
                ("ois/example.py",),
                "Explicit timeout behavior.",
            ),
        },
    )
    registry.register(
        Adapter(),
        SourceSpec("example.api.v1", "example", "http"),
        conformance=metadata,
    )

    row = IntegrationConformance(registry).audit().matrix[0]

    assert row["AUTH"] == "IMPLEMENTED"
    assert row["TIMEOUT"] == "IMPLEMENTED"
    assert row["CREDENTIAL"] == "UNKNOWN"
    assert row["LIVE TEST"] == "UNKNOWN"


def test_provider_metadata_rejects_unknown_columns() -> None:
    with pytest.raises(ValueError, match="unknown conformance metadata columns"):
        ProviderConformanceMetadata(
            source_id="example.api.v1",
            claims={"NOT A COLUMN": ConformanceEvidence("UNKNOWN")},
        )


def test_provider_metadata_requires_evidence_for_positive_claims() -> None:
    with pytest.raises(ValueError, match="require evidence"):
        ConformanceEvidence("IMPLEMENTED")


def test_provider_metadata_cannot_claim_runtime_verification() -> None:
    with pytest.raises(ValueError, match="runtime/CI evidence"):
        ConformanceEvidence("LIVE VERIFIED", ("tests/live_example.py",))


def test_registry_rejects_metadata_for_different_source() -> None:
    registry = SourceAdapterRegistry()

    with pytest.raises(ValueError, match="conformance source_id"):
        registry.register(
            Adapter(),
            SourceSpec("example.api.v1", "example", "http"),
            conformance=ProviderConformanceMetadata(
                source_id="other.api.v1",
                claims={},
            ),
        )
