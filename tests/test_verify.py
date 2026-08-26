from __future__ import annotations

import json
from pathlib import Path

from ois.verify import CheckResult, build_evidence, verify_artifact


def test_evidence_decision_is_derived_from_checks() -> None:
    document = build_evidence([
        CheckResult("one", ["one"], 0, True, "ok"),
        CheckResult("two", ["two"], 1, False, "failed"),
    ])
    assert document["conformance"] == "FAIL"
    assert document["activation_eligible"] is False


def test_evidence_hash_and_decision_are_verified(tmp_path: Path) -> None:
    document = build_evidence([CheckResult("one", ["one"], 0, True, "ok")])
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    valid, errors = verify_artifact(path)
    assert valid
    assert errors == []


def test_tampered_evidence_fails_hash_validation(tmp_path: Path) -> None:
    document = build_evidence([CheckResult("one", ["one"], 0, True, "ok")])
    document["conformance"] = "FAIL"
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    valid, errors = verify_artifact(path)
    assert not valid
    assert "evidence content hash mismatch" in errors


def test_production_activation_cannot_be_asserted(tmp_path: Path) -> None:
    document = build_evidence([CheckResult("one", ["one"], 0, True, "ok")])
    document["production_active"] = True
    path = tmp_path / "verification.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    valid, errors = verify_artifact(path)
    assert not valid
    assert "verification evidence cannot assert production activation" in errors
