from __future__ import annotations

import pytest

from ois.infrastructure.source_adapters import FileSourceAdapter, SourceAdapterRegistry
from ois.infrastructure.source_gateway import ApiSourceSocket, SourceGateway, SQLiteSourceLedger


def socket() -> ApiSourceSocket:
    ledger = SQLiteSourceLedger()
    return ApiSourceSocket(gateway=SourceGateway(evidence=ledger, outbox=ledger))


def test_socket_registers_and_ingests_source(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"id":"1","value":"live"}', encoding="utf-8")

    api_socket = socket()
    api_socket.register(FileSourceAdapter(source_id="file:test", path=str(path)))

    assert api_socket.sources() == ("file:test",)
    result = api_socket.ingest("file:test", tenant_id="tenant-1", workspace_id="workspace-1")

    assert result.records == 1
    assert result.evidence_ids
    assert result.event_ids


def test_socket_rejects_duplicate_source_ids(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"id":"1"}', encoding="utf-8")

    api_socket = socket()
    api_socket.register(FileSourceAdapter(source_id="file:test", path=str(path)))

    with pytest.raises(ValueError, match="already registered"):
        api_socket.register(FileSourceAdapter(source_id="file:test", path=str(path)))


def test_socket_status_reports_unknown_source() -> None:
    api_socket = socket()

    assert api_socket.status("missing").reason == "source_not_registered"


def test_registry_unregisters_explicitly(tmp_path) -> None:
    registry = SourceAdapterRegistry()
    path = tmp_path / "source.json"
    path.write_text('{"id":"1"}', encoding="utf-8")
    registry.register(FileSourceAdapter(source_id="file:test", path=str(path)))
    registry.unregister("file:test")

    assert registry.list() == ()
    with pytest.raises(KeyError, match="not registered"):
        registry.unregister("test:source")
