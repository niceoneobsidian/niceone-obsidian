"""Unified Phase B source-fabric orchestration boundary.

This module composes the existing registry, source socket, polling engine,
webhook gateway, cursor store, rate-limit/retry primitives, provenance, and
health telemetry without creating a second persistence path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import sleep

from ois.infrastructure.source_adapters import (
    AdapterResult,
    PollingEngine,
    PollingJob,
    PollingRun,
    SourceAdapter,
)
from ois.infrastructure.source_adapters.webhook_gateway import (
    WebhookGateway,
    WebhookRequest,
)
from ois.infrastructure.source_gateway import SourceGateway, SourceProvenance, SourceRequest
from ois.infrastructure.source_gateway.cursors import SourceCursor, SQLiteCursorStore
from ois.infrastructure.source_gateway.retry import RetryController, RetryDecision, RetryPolicy
from ois.infrastructure.source_gateway.socket import ApiSourceSocket
from ois.infrastructure.source_health import SourceHealthRegistry, SourceHealthSnapshot
from ois.infrastructure.source_registry import (
    SourceControlAPI,
    SourceDefinition,
    SourceStatus,
)


@dataclass(frozen=True)
class SourceFabricRun:
    source_id: str
    result: AdapterResult | None
    attempts: int
    retries: tuple[RetryDecision, ...]
    error: str | None = None


class SourceFabric:
    """Single orchestration surface for registered live sources."""

    def __init__(
        self,
        *,
        gateway: SourceGateway,
        source_control: SourceControlAPI,
        socket: ApiSourceSocket | None = None,
        cursor_store: SQLiteCursorStore | None = None,
        health: SourceHealthRegistry | None = None,
        retry_policy: RetryPolicy | None = None,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._gateway = gateway
        self._source_control = source_control
        self._socket = socket or ApiSourceSocket(
            gateway=gateway,
            source_control=source_control,
        )
        self._cursor_store = cursor_store or SQLiteCursorStore()
        self._health = health or SourceHealthRegistry()
        self._retry = RetryController(retry_policy)
        self._sleep = sleeper
        self._polling = PollingEngine(gateway=gateway)
        self._webhooks: dict[tuple[str, str, str], WebhookGateway] = {}

    @property
    def socket(self) -> ApiSourceSocket:
        return self._socket

    @property
    def source_control(self) -> SourceControlAPI:
        return self._source_control

    @property
    def health(self) -> SourceHealthRegistry:
        return self._health

    def register(
        self,
        source: SourceDefinition,
        adapter: SourceAdapter,
    ) -> SourceDefinition:
        definition = self._source_control.register(source)
        self._socket.register(adapter)
        if definition.mode == "poll":
            interval = definition.poll_interval_seconds or 60.0
            self._polling.register(
                PollingJob(
                    source_id=definition.source_id,
                    interval_seconds=interval,
                    adapter=adapter,
                    tenant_id=definition.tenant_id,
                    workspace_id=definition.workspace_id,
                    credential_id=definition.credential_id,
                )
            )
        return definition

    def enable(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition:
        return self._source_control.enable(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )

    def pause(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition:
        return self._source_control.pause(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )

    def disable(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition:
        return self._source_control.disable(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )

    def register_webhook(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        gateway: WebhookGateway,
    ) -> None:
        self._require_enabled(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)
        self._webhooks[(tenant_id, workspace_id, source_id)] = gateway

    def poll_once(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceFabricRun:
        definition = self._require_enabled(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if definition.mode != "poll":
            raise ValueError(f"source is not configured for polling: {source_id}")
        run = self._run_poll(source_id, tenant_id, workspace_id)
        return SourceFabricRun(
            source_id,
            run.result,
            1,
            (),
            run.error,
        )

    def poll_with_retry(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceFabricRun:
        definition = self._require_pollable(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if definition.mode != "poll":
            raise ValueError(f"source is not configured for polling: {source_id}")

        retries: list[RetryDecision] = []
        for attempt in range(1, self._retry.max_attempts + 1):
            run = self._run_poll(source_id, tenant_id, workspace_id)
            if run.error is None:
                return SourceFabricRun(source_id, run.result, attempt, tuple(retries))
            decision = self._retry.decide(
                attempt=attempt,
                retryable=True,
                reason=run.error,
            )
            retries.append(decision)
            if not decision.retry:
                return SourceFabricRun(
                    source_id,
                    None,
                    attempt,
                    tuple(retries),
                    error=run.error,
                )
            self._sleep(decision.delay_seconds)

        raise AssertionError("retry controller exceeded its configured attempt bound")

    def receive_webhook(self, request: WebhookRequest) -> AdapterResult:
        definition = self._require_enabled(
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
            source_id=request.source_id,
        )
        if definition.mode != "webhook":
            raise ValueError(f"source is not configured for webhooks: {request.source_id}")
        key = (request.tenant_id, request.workspace_id, request.source_id)
        gateway = self._webhooks.get(key)
        if gateway is None:
            raise KeyError(f"webhook gateway not registered: {request.source_id}")
        started = datetime.now(UTC)
        try:
            result = gateway.receive(request)
        except Exception as exc:
            self._record_failure(
                definition,
                error=f"{type(exc).__name__}: {exc}",
                started=started,
            )
            raise
        self._record_success(definition, started=started)
        return result

    def ingest_observation(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        record_id: str,
        payload: dict[str, object],
        provenance: SourceProvenance,
        connector_version: str = "fabric-v1",
        schema_version: str = "source.observation.v1",
    ) -> object:
        self._require_enabled(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        return self._gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=source_id,
                source_record_id=record_id,
                payload=payload,
                provenance=provenance,
                connector_version=connector_version,
                schema_version=schema_version,
            )
        )

    def cursor(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceCursor | None:
        self._require_source(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        return self._cursor_store.get(tenant_id, workspace_id, source_id)

    def advance_cursor(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        cursor: str,
        expected_version: int | None = None,
    ) -> SourceCursor:
        self._require_enabled(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        return self._cursor_store.advance(
            tenant_id,
            workspace_id,
            source_id,
            cursor,
            expected_version=expected_version,
        )

    def check_health(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceHealthSnapshot:
        definition = self._require_source(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        started = datetime.now(UTC)
        try:
            checks = self._socket.health(
                source_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                credential_id=definition.credential_id,
            )
            result = checks[0]
            if result.healthy:
                return self._record_success(definition, started=started)
            return self._record_failure(
                definition,
                error=result.reason or "source health check failed",
                started=started,
            )
        except Exception as exc:
            return self._record_failure(
                definition,
                error=f"{type(exc).__name__}: {exc}",
                started=started,
            )

    def _run_poll(
        self,
        source_id: str,
        tenant_id: str,
        workspace_id: str,
    ) -> PollingRun:
        started = datetime.now(UTC)
        run = self._polling.run_once(source_id)
        definition = self._require_source(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if run.error is None:
            self._record_success(definition, started=started)
        else:
            self._record_failure(definition, error=run.error, started=started)
        return run

    def _require_source(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceDefinition:
        return self._source_control.get(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )

    def _require_pollable(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceDefinition:
        source = self._require_source(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if SourceStatus(source.status or "") not in {
            SourceStatus.ENABLED,
            SourceStatus.DEGRADED,
        }:
            raise PermissionError(f"source is not pollable: {source_id} ({source.status})")
        return source

    def _require_enabled(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
    ) -> SourceDefinition:
        source = self._require_source(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )
        if SourceStatus(source.status or "") != SourceStatus.ENABLED:
            raise PermissionError(f"source is not enabled: {source_id} ({source.status})")
        return source

    def _record_success(
        self,
        definition: SourceDefinition,
        *,
        started: datetime,
    ) -> SourceHealthSnapshot:
        snapshot = self._health.record(
            tenant_id=definition.tenant_id,
            workspace_id=definition.workspace_id,
            source_id=definition.source_id,
            healthy=True,
            latency_ms=(datetime.now(UTC) - started).total_seconds() * 1000,
        )
        if SourceStatus(definition.status or "") == SourceStatus.DEGRADED:
            self._source_control.enable(
                tenant_id=definition.tenant_id,
                workspace_id=definition.workspace_id,
                source_id=definition.source_id,
            )
        return snapshot

    def _record_failure(
        self,
        definition: SourceDefinition,
        *,
        error: str,
        started: datetime,
    ) -> SourceHealthSnapshot:
        snapshot = self._health.record(
            tenant_id=definition.tenant_id,
            workspace_id=definition.workspace_id,
            source_id=definition.source_id,
            healthy=False,
            latency_ms=(datetime.now(UTC) - started).total_seconds() * 1000,
            error=error,
        )
        if SourceStatus(definition.status or "") == SourceStatus.ENABLED:
            self._source_control.degrade(
                tenant_id=definition.tenant_id,
                workspace_id=definition.workspace_id,
                source_id=definition.source_id,
            )
        return snapshot
