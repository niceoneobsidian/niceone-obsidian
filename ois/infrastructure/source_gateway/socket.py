"""Unified OIS API Source Socket.

This is the single application-facing entry point for governed live sources.
It owns registration, tenant-scoped ingestion, health checks, and adapter
discovery while delegating durable evidence/event handling to SourceGateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from ois.infrastructure.source_adapters.base import (
    AdapterHealth,
    AdapterResult,
    SourceAdapter,
    SourceAdapterRegistry,
)
from ois.infrastructure.source_gateway.gateway import SourceGateway
from ois.infrastructure.source_registry import SourceControlAPI, SourceDefinition


@dataclass(frozen=True)
class SocketStatus:
    source_id: str
    registered: bool
    healthy: bool | None
    reason: str | None = None


class ApiSourceSocket:
    """Single facade for adding and consuming live API/source connectors."""

    def __init__(
        self,
        *,
        gateway: SourceGateway,
        registry: SourceAdapterRegistry | None = None,
        source_control: SourceControlAPI | None = None,
    ) -> None:
        self._gateway = gateway
        self._registry = registry or SourceAdapterRegistry()
        self._source_control = source_control

    @property
    def gateway(self) -> SourceGateway:
        return self._gateway

    @property
    def source_control(self) -> SourceControlAPI | None:
        return self._source_control

    def register_definition(self, source: SourceDefinition) -> SourceDefinition:
        if self._source_control is None:
            raise RuntimeError("source control registry is not configured")
        return self._source_control.register(source)

    def list_definitions(
        self, *, tenant_id: str, workspace_id: str
    ) -> tuple[SourceDefinition, ...]:
        if self._source_control is None:
            raise RuntimeError("source control registry is not configured")
        return self._source_control.list(tenant_id=tenant_id, workspace_id=workspace_id)

    def register(self, adapter: SourceAdapter) -> None:
        """Register one connector; duplicate source IDs are rejected."""
        self._registry.register(adapter)

    def unregister(self, source_id: str) -> None:
        self._registry.unregister(source_id)

    def sources(self) -> tuple[str, ...]:
        return self._registry.list()

    def get(self, source_id: str) -> SourceAdapter:
        return self._registry.get(source_id)

    def _definition_for_ingest(
        self,
        *,
        source_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> SourceDefinition | None:
        if self._source_control is None:
            return None
        definition = self._source_control.get(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if not definition.enabled:
            raise PermissionError(f"source is disabled: {source_id}")
        return definition

    def ingest(
        self,
        source_id: str,
        *,
        tenant_id: str,
        workspace_id: str,
        credential_id: str | None = None,
    ) -> AdapterResult:
        """Fetch live data through a registered connector and commit it via the gateway."""
        definition = self._definition_for_ingest(
            source_id=source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        adapter = self._registry.get(source_id)
        return adapter.ingest(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            gateway=self._gateway,
            credential_id=credential_id or (definition.credential_id if definition else None),
        )

    def health(
        self,
        source_id: str | None = None,
        *,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        credential_id: str | None = None,
    ) -> tuple[AdapterHealth, ...]:
        """Return deterministic health, optionally using tenant-scoped credentials."""
        ids = (source_id,) if source_id else self._registry.list()
        results: list[AdapterHealth] = []
        for item in ids:
            adapter = self._registry.get(item)
            check = getattr(cast(Any, adapter), "health", None)
            if callable(check):
                results.append(
                    check(
                        gateway=self._gateway,
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        credential_id=credential_id,
                    )
                )
            else:
                results.append(
                    AdapterHealth(
                        source_id=item,
                        healthy=True,
                        checked_at=datetime.now(UTC).isoformat(),
                        reason="health_check_not_supported",
                    )
                )
        return tuple(results)

    def status(
        self,
        source_id: str,
        *,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        credential_id: str | None = None,
    ) -> SocketStatus:
        try:
            adapter = self._registry.get(source_id)
        except KeyError:
            return SocketStatus(source_id, False, None, "source_not_registered")
        health_check = getattr(cast(Any, adapter), "health", None)
        if not callable(health_check):
            return SocketStatus(source_id, True, True, "health_check_not_supported")
        health = health_check(
            gateway=self._gateway,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
        )
        return SocketStatus(source_id, True, health.healthy, health.reason)

    def ingest_payload(
        self,
        *,
        source_id: str,
        tenant_id: str,
        workspace_id: str,
        record_id: str,
        payload: dict[str, Any],
        credential_id: str | None = None,
        connector_version: str = "socket-v1",
        schema_version: str = "socket.payload.v1",
    ) -> AdapterResult:
        """Ingest an already-received webhook/stream payload through the same boundary."""
        definition = self._definition_for_ingest(
            source_id=source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        from ois.infrastructure.source_gateway import CredentialRef, SourceRequest

        effective_credential_id = credential_id or (
            definition.credential_id if definition else None
        )
        credential = None
        if effective_credential_id:
            credential = CredentialRef(
                credential_id=effective_credential_id,
                tenant_id=tenant_id,
                provider=source_id.split(":", 1)[0],
                scopes=(),
            )
        response = self._gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=source_id,
                source_record_id=record_id,
                payload=payload,
                credential=credential,
                connector_version=connector_version,
                schema_version=schema_version,
            )
        )
        return self._registry.response(source_id, [response])
