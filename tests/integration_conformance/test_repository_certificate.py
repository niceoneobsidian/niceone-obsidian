from pathlib import Path

from ois.integration.repository_certificate import (
    CertificatePolicy,
    build_repository_certificate,
)


def test_repository_certificate_is_hash_bound_and_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "ois/integrations/example").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)

    (tmp_path / "ois/integrations/example/source.py").write_text(
        '''
class ExampleSource:
    source_id = "example.api.v1"
    def ingest(self, **kwargs):
        return None
''',
        encoding="utf-8",
    )
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

    cert = build_repository_certificate(
        tmp_path,
        policy=CertificatePolicy(
            required=("ADAPTER", "STRUCTURAL TEST", "CONTRACT TEST", "CI GATE")
        ),
        commit="abc123",
    )

    assert cert.commit == "abc123"
    assert cert.certificate_hash
    assert cert.valid
    assert cert.report.matrix[0]["ADAPTER"] == "IMPLEMENTED"
    assert cert.report.matrix[0]["STRUCTURAL TEST"] == "TESTED"
    assert cert.report.matrix[0]["CONTRACT TEST"] == "TESTED"
    assert cert.report.matrix[0]["CI GATE"] == "TESTED"


def test_repository_certificate_does_not_promote_production_from_false_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "ois/integrations/example").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "manifests").mkdir()

    (tmp_path / "ois/integrations/example/source.py").write_text(
        'source_id = "example.api.v1"\n',
        encoding="utf-8",
    )
    (tmp_path / "manifests/example_production_readiness.json").write_text(
        '{"source_id":"example.api.v1","production_verified":false,"enabled":true}\n',
        encoding="utf-8",
    )

    cert = build_repository_certificate(tmp_path)
    assert cert.report.matrix[0]["PRODUCTION VERIFICATION"] == "UNKNOWN"
