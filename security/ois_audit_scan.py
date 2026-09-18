"""CI evidence compliance gate for OIS forensic evidence bundles.

The scanner is intentionally fail-closed: a missing signing key, malformed
bundle, broken content hash, invalid HMAC seal, or unsigned ledger event fails
the gate. It does not claim production readiness; it only verifies the bundle
contract supplied to the gate.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

REQUIRED_KEYS = (
    "structural_integrity_hash",
    "supervisor_cryptographic_seal",
    "historical_event_ledger",
)


class SecOpsEvidenceScanner:
    def __init__(self, verification_key: bytes) -> None:
        if not verification_key:
            raise ValueError("verification key must not be empty")
        self.key = verification_key

    @staticmethod
    def _canonical_hash(data: dict[str, Any]) -> str:
        snapshot = dict(data)
        snapshot["structural_integrity_hash"] = ""
        snapshot["supervisor_cryptographic_seal"] = ""
        canonical = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def scan_bundle_compliance(self, file_path: Path) -> bool:
        print(f"Analyzing evidence bundle: {file_path}")
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL: bundle is unreadable or invalid JSON: {exc}")
            return False

        if not isinstance(data, dict) or any(key not in data for key in REQUIRED_KEYS):
            print("FAIL: required evidence primitives are missing")
            return False

        target_hash = data["structural_integrity_hash"]
        target_seal = data["supervisor_cryptographic_seal"]
        ledger = data["historical_event_ledger"]
        if not isinstance(target_hash, str) or not isinstance(target_seal, str):
            print("FAIL: integrity hash/seal must be strings")
            return False
        if not isinstance(ledger, list):
            print("FAIL: historical event ledger must be a list")
            return False

        computed_hash = self._canonical_hash(data)
        if not hmac.compare_digest(computed_hash, target_hash):
            print("FAIL: structural integrity hash mismatch")
            return False

        computed_seal = hmac.new(
            self.key, computed_hash.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(computed_seal, target_seal):
            print("FAIL: supervisor cryptographic seal mismatch")
            return False

        for index, event in enumerate(ledger):
            if not isinstance(event, dict):
                print(f"FAIL: ledger event {index} is not an object")
                return False
            payload_hash = event.get("payload_hash")
            if not isinstance(payload_hash, str) or not payload_hash or payload_hash == "NULL":
                print(f"FAIL: ledger event {index} has no payload signature")
                return False

        print(f"PASS: {file_path} ({len(ledger)} ledger events verified)")
        return True


def run_ci_audit_pipeline(artifact_directory: Path, verification_key: bytes) -> int:
    if not artifact_directory.is_dir():
        print(f"FAIL: evidence directory does not exist: {artifact_directory}")
        return 1

    files = sorted(artifact_directory.rglob("*.json"))
    if not files:
        print(f"FAIL: no JSON evidence bundles found in {artifact_directory}")
        return 1

    scanner = SecOpsEvidenceScanner(verification_key)
    results = [scanner.scan_bundle_compliance(path) for path in files]
    if not all(results):
        print("CI GATE: evidence compliance failed")
        return 1

    print("CI GATE: all evidence bundles passed compliance checks")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify OIS evidence bundles")
    parser.add_argument(
        "--artifact-directory",
        type=Path,
        default=Path("artifacts/evidence"),
    )
    args = parser.parse_args()

    secret = os.getenv("OIS_KERNEL_AUDIT_KEY")
    if not secret:
        print("FAIL: OIS_KERNEL_AUDIT_KEY is required; no default signing secret is permitted")
        return 1
    return run_ci_audit_pipeline(args.artifact_directory, secret.encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
