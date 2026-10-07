from __future__ import annotations

import pytest

from ois.infrastructure.source_adapters import (
    AdapterHealth,
    FileSourceAdapter,
    SourceAdapterRegistry,
)
from ois.infrastructure.source_gateway import SourceGateway, SQLiteSourceLedger
from ois.infrastructure.source_gateway.socket import ApiSourceSocket


def test_socket_health_passes_keyword_arguments_to_adapters() -> None:
    class HealthAdapter:
        source_id = "health:test"

        def health(
            self,
            *,
            gateway: SourceGateway | None = None,
            tenant_id: str | None = None,
            workspace_id: str | None = None,
            credential_id: str | None = None,
        ) -> AdapterHealth:
            assert gateway is not None
            assert tenant_id == "tenant-1"
            assert workspace_id == "workspace-1"
            assert credential_id == "credential-1"
            return AdapterHealth(
                source_id=self.source_id,
                healthy=True,
                checked_at="2026-01-01T00:00:00+00:00",
            )

        def ingest(
            self,
            *,
            tenant_id: str,
            workspace_id: str,
            gateway: SourceGateway,
            credential_id: str | None = None,
        ):
            raise NotImplementedError

    api_socket = socket()
    api_socket.register(HealthAdapter())

    result = api_socket.health(
        "health:test",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        credential_id="credential-1",
    )

    assert result == (
        AdapterHealth(
            source_id="health:test",
            healthy=True,
            checked_at="2026-01-01T00:00:00+00:00",
        ),
    )


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


def test_socket_health_supports_adapters_without_health_method(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"id":"1"}', encoding="utf-8")
    api_socket = socket()
    api_socket.register(FileSourceAdapter(source_id="file:test", path=str(path)))

    result = api_socket.health("file:test")

    assert result[0].healthy is True
    assert result[0].reason == "health_check_not_supported"
