"""Stage 2: certificate wiring to registry, manifests and the declared inventory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ois.infrastructure.source_adapters.base import AdapterResult, SourceAdapterRegistry
from ois.infrastructure.source_adapters.bootstrap import (
    build_application_source_adapter_registry,
)
from ois.integration.inventory_drift import (
    DEFAULT_BACKLOG_PATH,
    DEFAULT_INVENTORY_PATH,
    compare_inventory_to_registry,
)
from ois.integration.provider_manifest_check import DEFAULT_MANIFEST_DIR
from ois.integration.repository_certificate import build_repository_certificate, main

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = build_application_source_adapter_registry()
IDS = sorted(REGISTRY.list())


def _inventory(tmp_path: Path, source_ids: list[str]) -> Path:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"providers": [{"source_id": s} for s in source_ids]}))
    return path


def test_certificate_records_manifest_status_per_provider() -> None:
    cert = build_repository_certificate(
        ROOT, registry=REGISTRY, manifest_dir=ROOT / DEFAULT_MANIFEST_DIR
    )
    providers = cert.provider_manifests["providers"]
    assert sorted(providers) == IDS
    assert all(v["status"] == "CONSISTENT" and v["sha256"] for v in providers.values())
    assert all("scopes" in v["unknown_fields"] for v in providers.values())


def test_certificate_marks_missing_and_invalid_manifests(tmp_path: Path) -> None:
    mdir = tmp_path / "m"
    shutil.copytree(ROOT / DEFAULT_MANIFEST_DIR, mdir)
    victims = {p: json.loads(p.read_text()) for p in sorted(mdir.glob("*.json"))}
    first, second, *_ = list(victims)
    first.unlink()
    doc = victims[second]
    doc["capabilities"].append("fabricated")
    second.write_text(json.dumps(doc))
    cert = build_repository_certificate(ROOT, registry=REGISTRY, manifest_dir=mdir)
    statuses = sorted(v["status"] for v in cert.provider_manifests["providers"].values())
    assert statuses.count("MISSING") == 1 and statuses.count("INVALID") == 1
    assert not cert.valid


def test_manifest_evidence_never_promotes_matrix_cells() -> None:
    plain = build_repository_certificate(ROOT, registry=REGISTRY)
    wired = build_repository_certificate(
        ROOT,
        registry=REGISTRY,
        manifest_dir=ROOT / DEFAULT_MANIFEST_DIR,
        inventory_path=ROOT / DEFAULT_INVENTORY_PATH,
    )
    assert plain.report.to_dict()["matrix"] == wired.report.to_dict()["matrix"]
    assert plain.mandatory_columns == wired.mandatory_columns


def test_hash_changes_when_manifest_content_changes(tmp_path: Path) -> None:
    mdir = tmp_path / "m"
    shutil.copytree(ROOT / DEFAULT_MANIFEST_DIR, mdir)
    before = build_repository_certificate(ROOT, registry=REGISTRY, manifest_dir=mdir)
    target = next(iter(sorted(mdir.glob("*.json"))))
    doc = json.loads(target.read_text())
    doc["metadata"]["note"] = "edited"
    target.write_text(json.dumps(doc))
    after = build_repository_certificate(ROOT, registry=REGISTRY, manifest_dir=mdir)
    assert before.certificate_hash != after.certificate_hash


BACKLOG_IDS = {
    "tiktok.display.v2",
    "rss.news",
    "tool.social.sociavault",
    "tool.social.bundle_social",
}


def _backlog(tmp_path: Path, mutate=None) -> Path:
    doc = json.loads((ROOT / DEFAULT_BACKLOG_PATH).read_text())
    if mutate:
        mutate(doc)
    path = tmp_path / "backlog.json"
    path.write_text(json.dumps(doc))
    return path


def _drift(inventory: Path | None = None, backlog: Path | None = None, registry=REGISTRY):
    return compare_inventory_to_registry(ROOT, registry, inventory, backlog)


def test_committed_backlog_explains_exactly_the_four_unregistered_providers() -> None:
    drift = _drift()
    assert set(drift.explained) == BACKLOG_IDS
    assert drift.unexplained == () and drift.failures() == () and not drift.drifted
    assert set(IDS) <= set(drift.in_both)


def test_backlog_lists_required_evidence_as_unknown_never_verified() -> None:
    doc = json.loads((ROOT / DEFAULT_BACKLOG_PATH).read_text())
    assert {e["source_id"] for e in doc["entries"]} == BACKLOG_IDS
    for entry in doc["entries"]:
        assert entry["registration_state"] == "NOT_REGISTERED"
        assert set(entry["required_evidence"].values()) == {"UNKNOWN"}
        assert set(entry["required_evidence"]) == {
            "client",
            "credential_injection",
            "scopes",
            "policy",
            "tests",
            "live_verification",
        }


def test_unexplained_drift_is_a_hard_failure(tmp_path: Path) -> None:
    inv = _inventory(tmp_path, [*IDS, *sorted(BACKLOG_IDS), "mystery.provider"])
    drift = _drift(inv)
    assert drift.unexplained == ("mystery.provider",)
    assert "mystery.provider:INVENTORY:unexplained-not-in-source-registry" in drift.failures()


def test_removing_backlog_makes_all_four_unexplained(tmp_path: Path) -> None:
    empty = _backlog(tmp_path, lambda d: d.__setitem__("entries", []))
    drift = _drift(backlog=empty)
    assert set(drift.unexplained) == BACKLOG_IDS
    assert len(drift.failures()) == 4


def test_missing_backlog_file_does_not_hide_drift(tmp_path: Path) -> None:
    drift = _drift(backlog=tmp_path / "absent.json")
    assert not drift.backlog_present
    assert set(drift.unexplained) == BACKLOG_IDS


def test_unexpected_registration_is_a_hard_failure(tmp_path: Path) -> None:
    drift = _drift(_inventory(tmp_path, [*IDS[1:], *sorted(BACKLOG_IDS)]))
    assert drift.registry_only == (IDS[0],)
    assert f"{IDS[0]}:INVENTORY:registered-but-not-in-inventory" in drift.failures()


def test_missing_and_unreadable_inventory_are_not_silent(tmp_path: Path) -> None:
    missing = _drift(tmp_path / "none.json")
    assert not missing.inventory_present and missing.drifted
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    unreadable = _drift(bad)
    assert unreadable.unreadable and "INVENTORY:unreadable" in unreadable.failures()


def test_stale_backlog_entry_for_registered_provider_fails(tmp_path: Path) -> None:
    def add(doc: dict) -> None:
        entry = dict(doc["entries"][0], source_id=IDS[0])
        doc["entries"].append(entry)

    drift = _drift(backlog=_backlog(tmp_path, add))
    assert f"{IDS[0]}:BACKLOG:stale-provider-is-registered" in drift.failures()


def test_backlog_entry_not_in_inventory_fails(tmp_path: Path) -> None:
    def add(doc: dict) -> None:
        doc["entries"].append(dict(doc["entries"][0], source_id="ghost.provider"))

    assert (
        "ghost.provider:BACKLOG:not-in-inventory"
        in _drift(backlog=_backlog(tmp_path, add)).failures()
    )


def test_backlog_cannot_claim_registration_or_verified_evidence(tmp_path: Path) -> None:
    def mutate(doc: dict) -> None:
        doc["entries"][0]["registration_state"] = "REGISTERED"
        doc["entries"][1]["required_evidence"]["live_verification"] = "VERIFIED"
        del doc["entries"][2]["required_evidence"]["policy"]

    failures = _drift(backlog=_backlog(tmp_path, mutate)).failures()
    assert any("unsupported-registration-claim" in f for f in failures)
    assert any("unsupported-evidence-claim=live_verification:VERIFIED" in f for f in failures)
    assert any("required-evidence-missing=policy" in f for f in failures)


def test_backlog_duplicate_and_unreadable_are_rejected(tmp_path: Path) -> None:
    dup = _backlog(tmp_path, lambda d: d["entries"].append(dict(d["entries"][0])))
    assert any(":BACKLOG:duplicate" in f for f in _drift(backlog=dup).failures())
    bad = tmp_path / "bad_backlog.json"
    bad.write_text("{oops")
    assert "BACKLOG:unreadable" in _drift(backlog=bad).failures()


class _PlaceholderAdapter:
    source_id = "tiktok.display.v2"

    def ingest(self, **_: object) -> AdapterResult:  # pragma: no cover - never executed
        raise AssertionError("placeholder must never execute")


def _registry_with_placeholder() -> SourceAdapterRegistry:
    registry = build_application_source_adapter_registry()
    registry.register(_PlaceholderAdapter())
    return registry


def test_placeholder_registration_cannot_satisfy_readiness() -> None:
    registry = _registry_with_placeholder()
    cert = build_repository_certificate(
        ROOT,
        registry=registry,
        manifest_dir=ROOT / DEFAULT_MANIFEST_DIR,
        inventory_path=ROOT / DEFAULT_INVENTORY_PATH,
    )
    assert not cert.valid
    assert "tiktok.display.v2:MANIFEST:missing" in cert.failures
    assert "tiktok.display.v2:CAPABILITY=UNKNOWN" in cert.failures
    assert "tiktok.display.v2:BACKLOG:stale-provider-is-registered" in cert.failures


def test_certificate_passes_with_backlog_explained_drift() -> None:
    cert = build_repository_certificate(
        ROOT,
        registry=REGISTRY,
        manifest_dir=ROOT / DEFAULT_MANIFEST_DIR,
        inventory_path=ROOT / DEFAULT_INVENTORY_PATH,
    )
    assert cert.valid
    assert set(cert.inventory_drift["registration_backlog"]) == BACKLOG_IDS
    assert cert.inventory_drift["unexplained_drift"] == []


def test_certificate_fails_on_unexplained_drift_by_default(tmp_path: Path) -> None:
    cert = build_repository_certificate(
        ROOT,
        registry=REGISTRY,
        inventory_path=_inventory(tmp_path, [*IDS, "mystery.provider"]),
    )
    assert not cert.valid
    assert "mystery.provider:INVENTORY:unexplained-not-in-source-registry" in cert.failures


def test_report_only_downgrade_keeps_drift_visible(tmp_path: Path) -> None:
    cert = build_repository_certificate(
        ROOT,
        registry=REGISTRY,
        inventory_path=_inventory(tmp_path, [*IDS, "mystery.provider"]),
        inventory_drift_report_only=True,
    )
    assert cert.valid
    assert cert.inventory_drift["unexplained_drift"] == ["mystery.provider"]


def test_cli_strict_fails_on_unexplained_drift_and_passes_when_explained(tmp_path: Path) -> None:
    out = tmp_path / "cert.json"
    base = ["--root", str(ROOT), "--output", str(out), "--strict"]
    assert main(base) == 0
    data = json.loads(out.read_text())
    assert set(data["inventory_drift"]["registration_backlog"]) == BACKLOG_IDS
    assert set(data["provider_manifests"]["providers"]) == set(IDS)
    inv = _inventory(tmp_path, [*IDS, "mystery.provider"])
    assert main([*base, "--inventory", str(inv)]) == 1
    assert main([*base, "--inventory", str(inv), "--report-only-inventory-drift"]) == 0
