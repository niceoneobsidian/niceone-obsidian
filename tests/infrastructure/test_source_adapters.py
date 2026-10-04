from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3

import pytest

from ois.infrastructure.source_adapters import (
    DatabaseSourceAdapter,
    FileSourceAdapter,
    HttpSourceAdapter,
    PollingSourceAdapter,
    PollPage,
    SourceAdapterRegistry,
    WebhookVerifier,
)
from ois.infrastructure.source_gateway import (
    InMemoryCredentialResolver,
    SourceGateway,
    SQLiteSourceLedger,
)
from ois.infrastructure.source_gateway.auth import AuthScheme


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


class _FakeHttpResponse:
    status = 200
    headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return b'{"ok": true}'

    def __enter__(self) -> _FakeHttpResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_http_adapter_authenticates_through_gateway() -> None:
    requests: list[object] = []

    def opener(request: object, timeout: float) -> _FakeHttpResponse:
        requests.append(request)
        return _FakeHttpResponse()

    ledger = SQLiteSourceLedger()
    gateway_instance = SourceGateway(
        credentials=InMemoryCredentialResolver({"cred": "token-123"}),
        evidence=ledger,
        outbox=ledger,
    )
    adapter = HttpSourceAdapter(
        source_id="google:test",
        url="https://example.test/resource",
        auth_scheme=AuthScheme.BEARER,
        opener=opener,
    )

    result = adapter.ingest(
        tenant_id="t1",
        workspace_id="w1",
        gateway=gateway_instance,
        credential_id="cred",
    )

    assert result.records == 1
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["Authorization"] == "Bearer token-123"


def test_http_adapter_requires_credential_for_authenticated_source() -> None:
    requests: list[object] = []

    def opener(request: object, timeout: float) -> _FakeHttpResponse:
        requests.append(request)
        return _FakeHttpResponse()

    gateway_instance, _ = gateway()
    adapter = HttpSourceAdapter(
        source_id="google:test",
        url="https://example.test/resource",
        auth_scheme=AuthScheme.BEARER,
        opener=opener,
    )

    with pytest.raises(PermissionError, match="authentication credential required"):
        adapter.ingest(
            tenant_id="t1",
            workspace_id="w1",
            gateway=gateway_instance,
        )

    assert requests == []
