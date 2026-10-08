"""Deterministic end-to-end credential security conformance suite."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from .core import ApiKeyManager, SecretRedactor
from .governance import AgentCredentialIssuer, AgentIdentity

def run_conformance() -> dict[str, bool]:
    manager = ApiKeyManager()
    record, raw = manager.create(owner_id="conformance", project_id="ois", service_id="test", environment="test", name="e2e", scopes={"read"}, expires_in=timedelta(minutes=5))
    results = {"key_hash": raw not in record.key_hash, "scope": manager.validate(raw, "read").id == record.id}
    manager.revoke(record.id, "conformance")
    try: manager.validate(raw)
    except PermissionError: results["revocation"] = True
    else: results["revocation"] = False
    results["redaction"] = "secret" not in SecretRedactor(["secret"]).redact("token=secret")
    now = datetime.now(UTC)
    identity = AgentIdentity("agent-conformance", "workload-conformance", "test", now, now + timedelta(minutes=5))
    cred = AgentCredentialIssuer().issue(identity, "read", {"read"}, ttl_seconds=60)
    results["agent_credential"] = cred.agent_id == identity.agent_id and cred.expires_at > now
    return results
