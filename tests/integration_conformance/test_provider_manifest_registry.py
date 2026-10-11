"""Regression tests: provider manifests must mirror the canonical registry."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from ois.infrastructure.source_adapters.bootstrap import (
    build_application_source_adapter_registry,
)
from ois.integration.provider_manifest import load_manifest
from ois.integration.provider_manifest_check import (
    DEFAULT_MANIFEST_DIR,
    validate_provider_manifests,
)
from ois.integration.repository_certificate import (
    CertificatePolicy,
    build_repository_certificate,
    main,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / DEFAULT_MANIFEST_DIR
REGISTRY = build_application_source_adapter_registry()
IDS = list(REGISTRY.list())
FILES = {sid: SRC_DIR / (sid.replace(":", "_").replace(".", "_") + ".json") for sid in IDS}


@pytest.fixture
def mdir(tmp_path: Path) -> Path:
    target = tmp_path / "providers"
    shutil.copytree(SRC_DIR, target)
    return target


def _edit(mdir: Path, sid: str, mutate) -> None:
    path = mdir / FILES[sid].name
    doc = json.loads(path.read_text())
    mutate(doc)
    path.write_text(json.dumps(doc))


def _failures(mdir: Path) -> tuple[str, ...]:
    return validate_provider_manifests(ROOT, REGISTRY, mdir)


def test_registry_has_four_providers_each_with_a_manifest_file() -> None:
    assert len(IDS) == 4
    for sid in IDS:
        assert FILES[sid].is_file(), sid


def test_committed_manifests_are_consistent_for_all_providers() -> None:
    assert validate_provider_manifests(ROOT, REGISTRY) == ()
    for sid in IDS:
        load_manifest(json.loads(FILES[sid].read_text()))


@pytest.mark.parametrize("sid", IDS)
def test_unproven_behaviour_is_unknown_and_empty(sid: str) -> None:
    doc = json.loads(FILES[sid].read_text())
    for field in ("tools", "scopes", "events"):
        assert doc[field] == []
    assert doc["policy"]["actions"] == []
    assert {
        "tools",
        "scopes",
        "policy_actions",
        "rate_limit",
        "retry",
        "idempotency",
        "events",
    } <= set(doc["unknown"])
    assert doc["verification"] == {
        "declared": True,
        "live": "UNKNOWN",
        "e2e": "UNKNOWN",
        "negative": "UNKNOWN",
        "production": "UNKNOWN",
    }
    assert doc["live"]["verified"] is False


@pytest.mark.parametrize("sid", IDS)
def test_missing_manifest_fails(mdir: Path, sid: str) -> None:
    (mdir / FILES[sid].name).unlink()
    assert f"{sid}:MANIFEST:missing" in _failures(mdir)


def test_missing_manifest_directory_fails_every_provider(tmp_path: Path) -> None:
    failures = _failures(tmp_path / "absent")
    assert all(f"{sid}:MANIFEST:missing" in failures for sid in IDS)


def test_orphan_manifest_for_unregistered_provider_fails(mdir: Path) -> None:
    doc = json.loads(FILES[IDS[0]].read_text())
    doc["provider"] = "ghost.provider"
    (mdir / "ghost.json").write_text(json.dumps(doc))
    assert "ghost.provider:MANIFEST:orphan-manifest-not-in-registry" in _failures(mdir)


def test_capability_mismatch_fails(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d["capabilities"].append("invented.capability"))
    assert f"{sid}:MANIFEST:capabilities-differ-from-SourceSpec" in _failures(mdir)


def test_protocol_and_version_mismatch_fails(mdir: Path) -> None:
    sid = IDS[1]

    def mutate(d: dict) -> None:
        d["metadata"]["version"] = "v99"
        d["metadata"]["protocol"] = "grpc"

    _edit(mdir, sid, mutate)
    failures = _failures(mdir)
    assert f"{sid}:MANIFEST:version-differs-from-SourceSpec" in failures
    assert f"{sid}:MANIFEST:protocol-differs-from-SourceSpec" in failures


def test_timeout_not_matching_adapter_fails(mdir: Path) -> None:
    sid = "sportmonks:football:v3"
    _edit(mdir, sid, lambda d: d["reliability"].__setitem__("timeout_seconds", 5.0))
    assert f"{sid}:MANIFEST:timeout-differs-from-adapter" in _failures(mdir)


def test_fabricated_evidence_path_fails(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d["evidence"]["claims"]["CAPABILITY"].append("ois/nope/fake.py"))
    assert any("evidence-missing=ois/nope/fake.py" in f for f in _failures(mdir))


def test_evidence_path_escaping_repository_fails(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d["evidence"]["claims"]["TIMEOUT"].append("../../etc/passwd"))
    assert any("evidence-outside-root" in f for f in _failures(mdir))


def test_real_file_not_in_registry_metadata_is_rejected(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d["evidence"]["claims"]["ADAPTER"].append("README.md"))
    assert any("evidence-not-in-registry-metadata=README.md" in f for f in _failures(mdir))


def test_adapter_path_differs_from_registry_metadata_fails(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d.__setitem__("adapter", "README.md"))
    assert f"{sid}:MANIFEST:adapter-path-differs-from-registry-metadata" in _failures(mdir)


def test_non_canonical_registration_fails(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d.__setitem__("registration", "hand-maintained-list"))
    assert f"{sid}:MANIFEST:registration-not-canonical-factory" in _failures(mdir)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["live"].__setitem__("mode", "read_write"),
        lambda d: d["live"].__setitem__("allow_writes", True),
    ],
)
def test_live_mode_escalation_is_rejected(mdir: Path, mutation) -> None:
    sid = IDS[0]
    _edit(mdir, sid, mutation)
    assert any(f.startswith(f"{sid}:MANIFEST:invalid:") for f in _failures(mdir))


@pytest.mark.parametrize("key", ["live", "e2e", "negative", "production"])
def test_verification_promotion_is_rejected(mdir: Path, key: str) -> None:
    sid = IDS[2]
    _edit(mdir, sid, lambda d: d["verification"].__setitem__(key, "LIVE_VERIFIED"))
    assert f"{sid}:MANIFEST:unsupported-verification-claim:{key}" in _failures(mdir)


def test_live_verified_flag_is_rejected(mdir: Path) -> None:
    sid = IDS[2]
    _edit(mdir, sid, lambda d: d["live"].__setitem__("verified", True))
    assert f"{sid}:MANIFEST:unsupported-verification-claim:live.verified" in _failures(mdir)


def test_declaring_scopes_without_evidence_fails(mdir: Path) -> None:
    sid = IDS[0]

    def mutate(d: dict) -> None:
        d["scopes"] = ["repo"]  # still listed in "unknown": contradictory

    _edit(mdir, sid, mutate)
    assert f"{sid}:MANIFEST:scopes-declared-unknown-but-populated" in _failures(mdir)


def test_removing_from_unknown_without_evidence_fails(mdir: Path) -> None:
    sid = IDS[0]

    def mutate(d: dict) -> None:
        d["scopes"] = ["repo"]
        d["unknown"].remove("scopes")

    _edit(mdir, sid, mutate)
    assert f"{sid}:MANIFEST:scopes-neither-unknown-nor-evidenced" in _failures(mdir)


def test_missing_required_manifest_section_is_invalid(mdir: Path) -> None:
    sid = IDS[0]
    _edit(mdir, sid, lambda d: d.pop("reliability"))
    assert any(f.startswith(f"{sid}:MANIFEST:invalid:") for f in _failures(mdir))


def test_unreadable_manifest_json_fails(mdir: Path) -> None:
    (mdir / "broken.json").write_text("{not json")
    assert "broken.json:MANIFEST:unreadable-json" in _failures(mdir)


def test_mandatory_columns_are_unchanged() -> None:
    assert CertificatePolicy().required == (
        "ADAPTER",
        "REGISTRATION",
        "CAPABILITY",
        "PROVENANCE",
        "EVIDENCE",
        "STRUCTURAL TEST",
        "CONTRACT TEST",
        "CI GATE",
    )


def test_certificate_valid_with_committed_manifests() -> None:
    cert = build_repository_certificate(ROOT, registry=REGISTRY, manifest_dir=SRC_DIR)
    assert cert.valid and cert.failures == ()
    assert all(
        row["LIVE TEST"] == "UNKNOWN" and row["PRODUCTION VERIFICATION"] == "UNKNOWN"
        for row in cert.report.to_dict()["matrix"]
    )


def test_certificate_fails_closed_on_missing_manifest(mdir: Path) -> None:
    (mdir / FILES[IDS[3]].name).unlink()
    cert = build_repository_certificate(ROOT, registry=REGISTRY, manifest_dir=mdir)
    assert not cert.valid
    assert f"{IDS[3]}:MANIFEST:missing" in cert.failures


def test_cli_strict_exits_nonzero_on_contradictory_manifest(mdir: Path, tmp_path: Path) -> None:
    _edit(mdir, IDS[0], lambda d: d["capabilities"].append("x"))
    out = tmp_path / "cert.json"
    rc = main(["--root", str(ROOT), "--output", str(out), "--strict", "--manifest-dir", str(mdir)])
    assert rc == 1
    assert not json.loads(out.read_text())["valid"]


def test_cli_strict_passes_with_committed_manifests(tmp_path: Path) -> None:
    out = tmp_path / "cert.json"
    assert main(["--root", str(ROOT), "--output", str(out), "--strict"]) == 0
    assert copy.deepcopy(json.loads(out.read_text()))["failures"] == []
