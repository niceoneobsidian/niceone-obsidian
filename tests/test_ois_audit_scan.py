import hashlib
import hmac
import json

from security.ois_audit_scan import SecOpsEvidenceScanner


def make_bundle(key: bytes) -> dict:
    data = {
        "structural_integrity_hash": "",
        "supervisor_cryptographic_seal": "",
        "historical_event_ledger": [
            {"event_type": "execution.completed", "payload_hash": hashlib.sha256(b"payload").hexdigest()}
        ],
    }
    computed_hash = SecOpsEvidenceScanner._canonical_hash(data)
    data["structural_integrity_hash"] = computed_hash
    data["supervisor_cryptographic_seal"] = hmac.new(
        key, computed_hash.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return data


def test_valid_bundle(tmp_path):
    key = b"test-key"
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(make_bundle(key)), encoding="utf-8")
    assert SecOpsEvidenceScanner(key).scan_bundle_compliance(path)


def test_tampered_bundle_fails(tmp_path):
    key = b"test-key"
    data = make_bundle(key)
    data["historical_event_ledger"][0]["event_type"] = "tampered"
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert not SecOpsEvidenceScanner(key).scan_bundle_compliance(path)


def test_wrong_key_fails(tmp_path):
    data = make_bundle(b"correct-key")
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert not SecOpsEvidenceScanner(b"wrong-key").scan_bundle_compliance(path)


def test_missing_payload_hash_fails(tmp_path):
    key = b"test-key"
    data = make_bundle(key)
    data["historical_event_ledger"][0]["payload_hash"] = "NULL"
    # Re-seal after the mutation so the ledger check, rather than hash checking,
    # is the failure under test.
    data["structural_integrity_hash"] = SecOpsEvidenceScanner._canonical_hash(data)
    data["supervisor_cryptographic_seal"] = hmac.new(
        key, data["structural_integrity_hash"].encode("ascii"), hashlib.sha256
    ).hexdigest()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert not SecOpsEvidenceScanner(key).scan_bundle_compliance(path)
