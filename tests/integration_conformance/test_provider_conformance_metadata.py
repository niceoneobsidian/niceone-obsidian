from pathlib import Path

import pytest

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry
from ois.infrastructure.source_adapters.bootstrap import build_application_source_adapter_registry
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


def test_canonical_providers_publish_explicit_conformance_metadata() -> None:
    registry = build_application_source_adapter_registry()

    expected = {
        "github.rest.user": {"AUTH", "CREDENTIAL", "TIMEOUT"},
        "google.drive.files": {"AUTH", "CREDENTIAL", "TIMEOUT"},
        "meta.graph.me": {"AUTH", "CREDENTIAL", "TIMEOUT"},
        "sportmonks:football:v3": {"AUTH", "CREDENTIAL", "TIMEOUT"},
    }

    for source_id, columns in expected.items():
        metadata = registry.conformance(source_id)
        assert metadata is not None
        assert metadata.source_id == source_id
        assert set(metadata.columns()) == columns

        for column in columns:
            claim = metadata.claim(column)
            assert claim is not None
            assert claim.status == "IMPLEMENTED"
            assert claim.evidence


def test_repository_certificate_validates_and_records_metadata_evidence(tmp_path: Path) -> None:
    evidence_path = tmp_path / "ois/example.py"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text('source_id = "example.api.v1"\n', encoding="utf-8")

    registry = SourceAdapterRegistry()
    registry.register(
        Adapter(),
        SourceSpec("example.api.v1", "example", "http"),
        conformance=ProviderConformanceMetadata(
            source_id="example.api.v1",
            claims={
                "AUTH": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/example.py",),
                    "Authentication contract evidence.",
                )
            },
        ),
    )

    certificate = build_repository_certificate(
        tmp_path,
        registry=registry,
        policy=CertificatePolicy(required=("AUTH",)),
    )

    assert certificate.valid
    assert any(
        item.kind == "CONFORMANCE_AUTH" and item.path == "ois/example.py"
        for item in certificate.evidence["example.api.v1"]
    )


def test_repository_certificate_rejects_missing_metadata_evidence(tmp_path: Path) -> None:
    registry = SourceAdapterRegistry()
    registry.register(
        Adapter(),
        SourceSpec("example.api.v1", "example", "http"),
        conformance=ProviderConformanceMetadata(
            source_id="example.api.v1",
            claims={
                "AUTH": ConformanceEvidence(
                    "IMPLEMENTED",
                    ("ois/missing.py",),
                )
            },
        ),
    )

    certificate = build_repository_certificate(
        tmp_path,
        registry=registry,
        policy=CertificatePolicy(required=("AUTH",)),
    )

    assert not certificate.valid
    assert "example.api.v1:AUTH:evidence-missing=ois/missing.py" in certificate.failures
