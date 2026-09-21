from datetime import UTC, datetime

import pytest

from ois.infrastructure.source_gateway import (
    CredentialRef, InMemoryCredentialResolver, OutboxEvent, RateLimitPolicy,
    SQLiteOutboxStore, SQLiteRawEvidenceWriter, SQLiteSourceLedger, SourceGateway, SourceRequest,
    TokenBucket, canonical_hash,
)


def gateway():
    evidence = SQLiteRawEvidenceWriter()
    outbox = SQLiteOutboxStore()
    resolver = InMemoryCredentialResolver({"cred-1": "secret"})
    return SourceGateway(evidence=evidence, outbox=outbox, credentials=resolver,
                         rate_limits={"tiktok": TokenBucket(RateLimitPolicy(1, 0.01))}), evidence, outbox


def test_gateway_enforces_tenant_credential_scope():
    g, _, _ = gateway()
    with pytest.raises(PermissionError):
        g.ingest(SourceRequest("tenant-a", "ws-a", "tiktok", "1", {"x": 1},
                               CredentialRef("cred-1", "tenant-b", "tiktok")))


def test_gateway_persists_hashed_evidence_and_outbox():
    g, evidence, outbox = gateway()
    result = g.ingest(SourceRequest("tenant-a", "ws-a", "tiktok", "1", {"x": 1},
                                    CredentialRef("cred-1", "tenant-a", "tiktok"),
                                    connector_version="tiktok-v1"))
    assert result.accepted
    assert result.payload_hash == canonical_hash({"x": 1})
    stored = evidence.get(result.evidence_id)
    assert stored is not None
    assert stored.payload_hash == result.payload_hash
    assert len(outbox.pending()) == 1


def test_gateway_rate_limits_before_external_side_effects():
    g, _, outbox = gateway()
    first = g.ingest(SourceRequest("tenant-a", "ws-a", "tiktok", "1", {"x": 1}))
    second = g.ingest(SourceRequest("tenant-a", "ws-a", "tiktok", "2", {"x": 2}))
    assert first.accepted
    assert not second.accepted
    assert second.reason == "rate_limited"
    assert len(outbox.pending()) == 1


def test_atomic_ledger_commits_evidence_and_outbox_together():
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=ledger, outbox=ledger)
    result = gateway.ingest(SourceRequest("tenant-a", "ws-a", "fixture", "1", {"x": 1}))
    assert result.accepted
    assert ledger.evidence(result.evidence_id) is not None
    assert [e.event_id for e in ledger.pending()] == [result.event_id]


def test_outbox_is_idempotent_and_ordered():
    store = SQLiteOutboxStore()
    now = datetime.now(UTC)
    event = OutboxEvent("e1", "t", "w", "test", "a", {"n": 1}, now)
    assert store.append(event)
    assert not store.append(event)
    assert [e.event_id for e in store.pending()] == ["e1"]
    store.mark_published("e1")
    assert store.pending() == ()
