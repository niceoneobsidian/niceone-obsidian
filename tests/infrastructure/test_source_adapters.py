from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3

from ois.infrastructure.source_adapters import (
    DatabaseSourceAdapter,
    FileSourceAdapter,
    PollingSourceAdapter,
    PollPage,
    SourceAdapterRegistry,
    WebhookVerifier,
)
from ois.infrastructure.source_gateway import SourceGateway, SQLiteSourceLedger


def gateway() -> tuple[SourceGateway, SQLiteSourceLedger]:
    ledger = SQLiteSourceLedger()
    return SourceGateway(evidence=ledger, outbox=ledger), ledger


def test_webhook_requires_valid_signature_and_persists() -> None:
    gateway_instance, ledger = gateway()
    verifier = WebhookVerifier(secret=b"secret")
    payload = json.dumps({"event": "created"}).encode()
    signature = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()
    result = verifier.ingest(
        tenant_id="t1",
        workspace_id="w1",
        source_id="webhook:test",
        record_id="evt-1",
        payload=payload,
        signature=signature,
        gateway=gateway_instance,
    )
    assert result.records == 1
    assert ledger.evidence(result.evidence_ids[0]) is not None


def test_file_adapter_uses_gateway_evidence(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"id":"1","value":"live"}', encoding="utf-8")
    gateway_instance, ledger = gateway()
    result = FileSourceAdapter(source_id="file:test", path=str(path)).ingest(
        tenant_id="t1", workspace_id="w1", gateway=gateway_instance
    )
    assert result.records == 1
    assert ledger.evidence(result.evidence_ids[0]) is not None


def test_database_adapter_ingests_rows() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE source (id TEXT, value TEXT)")
    connection.executemany("INSERT INTO source VALUES (?, ?)", [("1", "a"), ("2", "b")])
    connection.commit()

    gateway_instance, ledger = gateway()
    adapter = DatabaseSourceAdapter(
        source_id="db:test",
        connection_factory=lambda: connection,
        query="SELECT id, value FROM source",
    )
    result = adapter.ingest(tenant_id="t1", workspace_id="w1", gateway=gateway_instance)
    assert result.records == 2
    assert all(ledger.evidence(item) is not None for item in result.evidence_ids)


def test_polling_advances_cursor_after_gateway_acceptance() -> None:
    cursor = [None]
    gateway_instance, ledger = gateway()

    def fetch(value: str | None) -> PollPage:
        if value is None:
            return PollPage(({"id": "1", "value": "a"},), "next")
        return PollPage(({"id": "2", "value": "b"},), None)

    adapter = PollingSourceAdapter(
        source_id="poll:test",
        fetch_page=fetch,
        get_cursor=lambda: cursor[0],
        set_cursor=lambda value: cursor.__setitem__(0, value),
    )
    result = adapter.ingest(tenant_id="t1", workspace_id="w1", gateway=gateway_instance)
    assert result.records == 2
    assert cursor[0] is None
    assert len(ledger.pending()) == 2


def test_registry_is_deterministic() -> None:
    registry = SourceAdapterRegistry()
    assert registry.list() == ()
