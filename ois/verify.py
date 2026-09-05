"""Canonical local CI verifier and conformance evidence producer for OIS.

The verifier proves repository conformance only. It MUST NOT assert or imply
production activation. Production promotion consumes independently verified
runtime evidence through the production control plane.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / ".ois" / "evidence" / "verification.json"
SCHEMA = "ois.conformance.v2"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required_tool: str


CHECKS = (
    Check("Ruff lint", ("ruff", "check", "."), "ruff"),
    Check("Ruff format", ("ruff", "format", "--check", "."), "ruff"),
    Check("Mypy", ("python", "-m", "mypy", "ois"), "mypy"),
    Check(
        "Bandit",
        ("bandit", "-r", ".", "-x", "./.git,./.venv,./venv,./tests", "-lll", "-iii"),
        "bandit",
    ),
    Check("Gitleaks", ("gitleaks", "detect", "--no-banner", "--redact"), "gitleaks"),
    Check("License compliance", ("pip-licenses", "--format=csv"), "pip-licenses"),
    Check("OIS governance", ("python", "scripts/ois_governance_check.py"), "python"),
    Check("Tests", ("python", "-m", "pytest", "-q"), "pytest"),
)


def executable(check: Check) -> str | None:
    if check.command[0] == "python":
        return sys.executable
    return shutil.which(check.required_tool)


def run_check(check: Check) -> dict[str, Any]:
    exe = executable(check)
    if exe is None:
        return {
            "name": check.name,
            "command": list(check.command),
            "status": "NOT_INSTALLED",
            "returncode": None,
            "output": "required executable is not installed",
        }

    command = (exe, *check.command[1:]) if check.command[0] == "python" else check.command
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "name": check.name,
        "command": list(command),
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "output": proc.stdout.strip(),
    }


def git_value(*args: str) -> str:
    proc = subprocess.run(
        ("git", *args),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.stdout.strip()


def git_commit_exists(commit_sha: str) -> bool:
    if not SHA_RE.fullmatch(commit_sha):
        return False
    proc = subprocess.run(
        ("git", "cat-file", "-e", f"{commit_sha}^{{commit}}"),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode == 0


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def content_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("content_hash", None)
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def build_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    commit_sha = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    status = git_value("status", "--porcelain")
    passed = bool(results) and all(result["status"] == "PASS" for result in results)
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": git_value("config", "--get", "remote.origin.url"),
        "commit_sha": commit_sha,
        "branch": branch,
        "working_tree": "clean" if not status else "dirty",
        "checks": results,
        "conformance": (
            "PASS"
            if passed and not status and git_commit_exists(commit_sha)
            else "FAIL"
        ),
        "evidence_class": "CONFORMANCE",
        "production_promotion_eligible": False,
        "activation_eligible": False,
        "activation_note": (
            "OIS conformance evidence is not production-promotion evidence. "
            "Production activation requires independently verified runtime evidence, "
            "authorization, and the governed promotion controller."
        ),
    }
    document["content_hash"] = content_hash(document)
    return document


def verify_artifact(artifact: Path = EVIDENCE_PATH) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        document = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"unable to read evidence artifact: {exc}"]

    if not isinstance(document, dict):
        return False, ["verification evidence must be a JSON object"]

    if document.get("schema") != SCHEMA:
        errors.append("unsupported evidence schema")
    if document.get("production_promotion_eligible") is not False:
        errors.append("conformance evidence cannot be production-promotion eligible")
    if document.get("activation_eligible") is not False:
        errors.append("conformance evidence cannot assert activation eligibility")
    forbidden = (
        "production_promoted",
        "production_active",
        "PRODUCTION PROMOTED",
        "PROD_ACTIVE",
    )
    if any(key in document for key in forbidden):
        errors.append("verification evidence cannot assert production activation")

    commit_sha = str(document.get("commit_sha", ""))
    if not SHA_RE.fullmatch(commit_sha):
        errors.append("evidence is not bound to a valid commit SHA")
    elif not git_commit_exists(commit_sha):
        errors.append("evidence commit SHA does not resolve to a repository commit")

    if document.get("working_tree") != "clean":
        errors.append("conformance evidence requires a clean working tree")

    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("evidence contains no checks")
    else:
        for index, item in enumerate(checks):
            if not isinstance(item, dict):
                errors.append(f"evidence check {index} is not an object")
                continue
            if item.get("status") != "PASS":
                errors.append(f"evidence check {index} is not PASS")

    if document.get("conformance") != "PASS":
        errors.append("conformance result is not PASS")
    if document.get("content_hash") != content_hash(document):
        errors.append("evidence content hash mismatch")
    return not errors, errors


def verify(artifact: Path = EVIDENCE_PATH) -> int:
    results = [run_check(check) for check in CHECKS]
    document = build_evidence(results)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    valid, errors = verify_artifact(artifact)
    print(f"OIS CONFORMANCE: {document['conformance']}")
    print(f"Evidence: {artifact}")
    print(f"Commit: {document['commit_sha']}")
    for result in results:
        print(f"{result['status']:>12} {result['name']}: {' '.join(result['command'])}")
    if not valid:
        for error in errors:
            print(f"EVIDENCE ERROR: {error}")
        return 2
    return 0


def main() -> int:
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
