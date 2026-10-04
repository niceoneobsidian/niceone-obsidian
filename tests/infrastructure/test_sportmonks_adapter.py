from __future__ import annotations

import json
from email.message import Message
from urllib.request import Request

import pytest

from ois.infrastructure.source_adapters import (
    SourceAdapterRegistry,
    SportmonksFootballAdapter,
)
from ois.infrastructure.source_gateway import (
    InMemoryCredentialResolver,
    SourceGateway,
    SQLiteSourceLedger,
)


class FakeResponse:
    status = 200

    def __init__(self, payload: object) -> None:
        self._raw = json.dumps(payload).encode()
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_sportmonks_adapter_registers_explicit_contract() -> None:
    registry = SourceAdapterRegistry()
    adapter = SportmonksFootballAdapter.register(registry)
    assert registry.list() == ("sportmonks:football:v3",)
    assert registry.spec(adapter.source_id).provider == "sportmonks"
    assert registry.spec(adapter.source_id).version == "v3"


def test_sportmonks_adapter_uses_authorization_and_gateway_evidence() -> None:
    calls: list[object] = []

    def opener(request: Request, *, timeout: float) -> FakeResponse:
        calls.append(request)
        headers = request.headers
        assert headers["Authorization"] == "secret-token"
        assert "include=participants%3Bscores%3Bstate" in request.full_url
        return FakeResponse({"data": [{"id": 123, "name": "Example FC vs Example United"}]})

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        credentials=InMemoryCredentialResolver({"sm-1": "secret-token"}),
        evidence=ledger,
        outbox=ledger,
    )
    adapter = SportmonksFootballAdapter(opener=opener)
    result = adapter.ingest(
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        gateway=gateway,
        credential_id="sm-1",
    )

    assert result.records == 1
    assert len(calls) == 1
    evidence = ledger.evidence(result.evidence_ids[0])
    assert evidence is not None
    assert evidence.source_id == "sportmonks:football:v3"
    assert ledger.pending()[0].payload["provenance"]["provider"] == "sportmonks"


def test_sportmonks_adapter_rejects_missing_or_cross_scope_credentials() -> None:
    gateway = SourceGateway(
        credentials=InMemoryCredentialResolver({"sm-1": "secret-token"}),
        evidence=SQLiteSourceLedger(),
        outbox=SQLiteSourceLedger(),
    )
    adapter = SportmonksFootballAdapter(opener=lambda request, timeout: FakeResponse({"data": []}))

    with pytest.raises(KeyError):
        adapter.ingest(
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            gateway=gateway,
            credential_id="missing",
        )
