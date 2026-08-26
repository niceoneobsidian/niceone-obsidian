"""Canonical OIS repository verification and conformance evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = ROOT / ".ois" / "evidence" / "verification.json"
SCHEMA_VERSION = "ois.verification.v1"


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: list[str]
    returncode: int
    passed: bool
    output: str


def _run(command: list[str]) -> CheckResult:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        return CheckResult(command[0], command, 127, False, str(exc))
    return CheckResult(
        command[0],
        command,
        result.returncode,
        result.returncode == 0,
        result.stdout[-12000:],
    )


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def _canonical(document: dict[str, object]) -> bytes:
    unsigned = dict(document)
    unsigned.pop("content_hash", None)
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()


def _hash(document: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(document)).hexdigest()


def verify_artifact(path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"unable to read evidence artifact: {exc}"]

    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported evidence schema")
    if document.get("content_hash") != _hash(document):
        errors.append("evidence content hash mismatch")

    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("evidence contains no checks")
    else:
        calculated = all(
            isinstance(item, dict) and bool(item.get("passed")) for item in checks
        )
        if document.get("conformance") != ("PASS" if calculated else "FAIL"):
            errors.append("conformance decision does not match observed checks")

    if "production_promoted" in document or "production_active" in document:
        errors.append("verification evidence cannot assert production activation")
    return not errors, errors


def build_evidence(results: list[CheckResult]) -> dict[str, object]:
    passed = all(result.passed for result in results)
    document: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "verification_run_id": str(uuid4()),
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": _git("config", "--get", "remote.origin.url"),
        "commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "working_tree": "clean" if not _git("status", "--porcelain") else "dirty",
        "python": sys.version,
        "platform": platform.platform(),
        "checks": [asdict(result) for result in results],
        "conformance": "PASS" if passed else "FAIL",
        "activation_eligible": False,
        "activation_note": (
            "P0 verification establishes conformance evidence only; production activation "
            "requires a separate governed promotion gate."
        ),
    }
    document["content_hash"] = _hash(document)
    return document


def verify(artifact: Path = DEFAULT_ARTIFACT) -> int:
    commands = [
        ["git", "diff", "--check"],
        [sys.executable, "-m", "compileall", "-q", "ois"],
        [sys.executable, "-m", "pytest", "-q"],
    ]
    results = [_run(command) for command in commands]
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
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} {result.name}: {' '.join(result.command)}")
    if not valid:
        for error in errors:
            print(f"EVIDENCE ERROR: {error}")
        return 2
    return 0 if document["conformance"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ois verify")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args(argv)
    return verify(args.artifact)
