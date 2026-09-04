import json

from ois.verify import CHECKS, build_evidence, content_hash, verify_artifact


def test_local_ci_covers_all_repository_ci_gates() -> None:
    names = {check.name for check in CHECKS}
    assert names == {
        "Ruff lint",
        "Ruff format",
        "Mypy",
        "Bandit",
        "Gitleaks",
        "License compliance",
        "OIS governance",
        "Tests",
    }


def test_python_checks_use_current_interpreter() -> None:
    python_checks = [check for check in CHECKS if check.command[0] == "python"]
    assert {check.required_tool for check in python_checks} == {"python"}


def test_conformance_evidence_can_never_claim_production_activation() -> None:
    results = [
        {"name": check.name, "command": list(check.command), "status": "PASS", "returncode": 0, "output": ""}
        for check in CHECKS
    ]
    evidence = build_evidence(results)
    assert evidence["evidence_class"] == "CONFORMANCE"
    assert evidence["production_promotion_eligible"] is False
    assert evidence["activation_eligible"] is False
    assert "production_active" not in evidence
    assert evidence["content_hash"] == content_hash(evidence)


def test_tampered_or_self_attested_promotion_evidence_is_rejected(tmp_path) -> None:
    results = [
        {"name": check.name, "command": list(check.command), "status": "PASS", "returncode": 0, "output": ""}
        for check in CHECKS
    ]
    evidence = build_evidence(results)
    evidence["production_active"] = True
    artifact = tmp_path / "verification.json"
    artifact.write_text(json.dumps(evidence), encoding="utf-8")

    valid, errors = verify_artifact(artifact)
    assert valid is False
    assert any("production activation" in error for error in errors)


def test_failed_gate_cannot_be_conformance_pass() -> None:
    results = [
        {"name": check.name, "command": list(check.command), "status": "PASS", "returncode": 0, "output": ""}
        for check in CHECKS
    ]
    results[-1]["status"] = "FAIL"
    evidence = build_evidence(results)
    assert evidence["conformance"] == "FAIL"
    assert evidence["production_promotion_eligible"] is False
