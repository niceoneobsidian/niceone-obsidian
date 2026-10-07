from pathlib import Path

import pytest

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry
from ois.infrastructure.source_gateway.contracts import SourceSpec
from ois.integration.repository_certificate import (
    CertificatePolicy,
    build_repository_certificate,
)


class ExampleAdapter:
    source_id = "example.api.v1"

    def ingest(self, *, tenant_id, workspace_id, gateway, credential_id=None):
        raise NotImplementedError


class OtherAdapter:
    source_id = "other.api.v1"

    def ingest(self, *, tenant_id, workspace_id, gateway, credential_id=None):
        raise NotImplementedError


def _registry(*adapters) -> SourceAdapterRegistry:
    registry = SourceAdapterRegistry()
    for adapter in adapters:
        registry.register(
            adapter,
            SourceSpec(
                source_id=adapter.source_id,
                provider=adapter.source_id.split(".", 1)[0],
                protocol="http",
                capabilities=("read",),
            ),
        )
    return registry


def test_repository_certificate_is_hash_bound_and_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)

    (tmp_path / "tests/test_example_structure.py").write_text(
        'def test_example(): assert "example.api.v1"\n',
        encoding="utf-8",
    )
    (tmp_path / "tests/test_example_contract.py").write_text(
        'def test_example_contract(): assert "example.api.v1"\n',
        encoding="utf-8",
    )
    (tmp_path / ".github/workflows/integration-conformance.yml").write_text(
        "name: Integration Conformance\nrun: pytest\n",
        encoding="utf-8",
    )

    registry = _registry(ExampleAdapter())

    cert = build_repository_certificate(
        tmp_path,
        registry=registry,
        policy=CertificatePolicy(
            required=("ADAPTER", "STRUCTURAL TEST", "CONTRACT TEST", "CI GATE")
        ),
        commit="abc123",
    )

    assert cert.valid
    assert cert.commit == "abc123"
    assert cert.report.matrix[0]["ADAPTER"] == "IMPLEMENTED"
    assert cert.report.matrix[0]["REGISTRATION"] == "IMPLEMENTED"
    assert cert.report.matrix[0]["CAPABILITY"] == "IMPLEMENTED"
    assert cert.report.matrix[0]["STRUCTURAL TEST"] == "TESTED"
    assert cert.report.matrix[0]["CONTRACT TEST"] == "TESTED"
    assert cert.report.matrix[0]["CI GATE"] == "TESTED"


def test_repository_certificate_is_invalid_for_empty_registry(tmp_path: Path) -> None:
    registry = SourceAdapterRegistry()

    cert = build_repository_certificate(
        tmp_path,
        registry=registry,
    )

    assert not cert.valid
    assert "REGISTRY_EMPTY" in cert.failures


def test_repository_certificate_does_not_promote_production_from_false_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "manifests").mkdir()

    (tmp_path / "manifests/example_production_readiness.json").write_text(
        '{"source_id":"example.api.v1","production_verified":false,"enabled":true}\n',
        encoding="utf-8",
    )

    cert = build_repository_certificate(
        tmp_path,
        registry=_registry(ExampleAdapter()),
    )

    row = cert.report.matrix[0]
    assert row["PRODUCTION VERIFICATION"] == "UNKNOWN"


def test_repository_certificate_does_not_borrow_unrelated_provider_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)

    (tmp_path / "tests/test_other_contract.py").write_text(
        'def test_other(): assert "other.api.v1 retry event_id provenance"\n',
        encoding="utf-8",
    )
    (tmp_path / ".github/workflows/integration-conformance.yml").write_text(
        "name: Integration Conformance\nrun: pytest\n",
        encoding="utf-8",
    )

    cert = build_repository_certificate(
        tmp_path,
        registry=_registry(ExampleAdapter(), OtherAdapter()),
    )

    row = next(
        record.row() for record in cert.report.records if record.source_id == "example.api.v1"
    )

    assert row["RETRY"] == "UNKNOWN"
    assert row["EVENTS"] == "UNKNOWN"
    assert row["PROVENANCE"] == "IMPLEMENTED"


def test_repository_certificate_does_not_promote_production_from_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "manifests").mkdir()

    (tmp_path / "manifests/example_production_readiness.json").write_text(
        '{"source_id":"example.api.v1","production_verified":true}\n',
        encoding="utf-8",
    )

    cert = build_repository_certificate(
        tmp_path,
        registry=_registry(ExampleAdapter()),
    )

    assert cert.report.matrix[0]["PRODUCTION VERIFICATION"] == "UNKNOWN"


def test_repository_certificate_requires_registered_source(tmp_path: Path) -> None:
    registry = SourceAdapterRegistry()

    with pytest.raises(KeyError):
        registry.get("example.api.v1")
