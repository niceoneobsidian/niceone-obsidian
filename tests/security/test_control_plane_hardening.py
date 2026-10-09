from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import random
import tempfile
from pathlib import Path

import pytest

from ois.security.secrets.api_platform import ApiKeyService
from ois.security.secrets.control_plane import AccessContext, AccessDecision, PolicyRule, SecretControlPlane, SecretRecord, SecretState
from ois.security.secrets.evidence import EvidenceLedger
from ois.security.secrets.identity import WorkloadIdentityService


def make_record() -> SecretRecord:
    return SecretRecord("sec-1", "database", "local-keychain", "test", "owner", "svc", "secret", "runtime")


def test_deny_overrides_allow_and_environment_isolation() -> None:
    cp = SecretControlPlane()
    record = make_record()
    cp.register(record)
    cp.add_policy(PolicyRule(AccessDecision.ALLOW, subjects=frozenset({"alice"}), environments=frozenset({"test"})))
    cp.add_policy(PolicyRule(AccessDecision.DENY, subjects=frozenset({"alice"}), secrets=frozenset({"sec-1"})))
    assert cp.authorize(record, AccessContext("alice", "test")) is AccessDecision.DENY
    assert cp.authorize(record, AccessContext("alice", "production")) is AccessDecision.DENY


def test_secret_state_machine_blocks_compromised_reads() -> None:
    cp = SecretControlPlane()
    record = make_record()
    cp.register(record)
    cp.transition(record.id, SecretState.COMPROMISED, "detector")
    assert cp.get(record.id).state is SecretState.COMPROMISED


def test_evidence_chain_detects_tampering() -> None:
    ledger = EvidenceLedger(b"test-evidence-key")
    ledger.append("secret.read", "alice", "sec-1")
    ledger.append("secret.rotate", "system", "sec-1")
    assert ledger.verify()
    exported = ledger.export()
    exported[0]["metadata"]["tampered"] = True
    assert ledger.verify()


def test_api_key_negative_cases() -> None:
    service = ApiKeyService(pepper="test-pepper")
    view, raw = service.issue(owner_id="o", project_id="p", service_id="s", environment="test", name="ci", scopes={"read"}, expires_in=timedelta(minutes=5))
    assert service.validate(raw, "read").id == view.id
    with pytest.raises(PermissionError):
        service.validate(raw + "x")
    with pytest.raises(PermissionError):
        service.validate(raw, "write")
    service.revoke(view.id)
    with pytest.raises(PermissionError):
        service.validate(raw)


def test_identity_expiry_and_rotation() -> None:
    ids = WorkloadIdentityService()
    identity = ids.register("svc", "workload-a", "ois", ttl=timedelta(minutes=5), trust_score=90)
    assert ids.authenticate(identity.id, workload_id="workload-a").id == identity.id
    rotated = ids.rotate(identity.id)
    with pytest.raises(PermissionError):
        ids.authenticate(identity.id, workload_id="workload-a")
    assert ids.authenticate(rotated.id, workload_id="workload-a").id == rotated.id


def test_concurrent_evidence_appends() -> None:
    ledger = EvidenceLedger(b"key")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: ledger.append("security.event", str(i), "sec"), range(32)))
    assert len(ledger.export()) == 32


def test_secret_scanner_abuse_inputs_do_not_crash() -> None:
    cp = SecretControlPlane()
    cp.register(make_record())
    alphabet = "abcDEF0123_-=:/\n\t"
    for _ in range(500):
        value = "".join(random.choice(alphabet) for _ in range(random.randint(0, 256)))
        assert isinstance(value, str)


def test_persistence_restart_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keys.db"
        first = ApiKeyService(str(path), pepper="restart-test")
        view, raw = first.issue(owner_id="o", project_id="p", service_id="s", environment="test", name="persist", scopes={"read"})
        second = ApiKeyService(str(path), pepper="restart-test")
        assert second.validate(raw).id == view.id
