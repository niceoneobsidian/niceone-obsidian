from __future__ import annotations

from dataclasses import dataclass
import pytest

from ois.infrastructure.source_adapters.base import AdapterResult
from ois.infrastructure.source_adapters.webhook_gateway import WebhookGateway, WebhookRequest
from ois.infrastructure.source_fabric import SourceFabric
from ois.infrastructure.source_gateway import (
    SourceGateway,
    SourceProvenance,
    SQLiteCursorStore,
    SQLiteIdempotencyStore,
    SQLiteSourceLedger,
    WebhookSecurity,
    WebhookSecurityPolicy,
)
from ois.infrastructure.source_gateway.retry import RetryController, RetryPolicy
from ois.infrastructure.source_health import SourceHealthRegistry
from ois.infrastructure.source_registry import (
    SourceControlAPI,
    SourceDefinition,
    SourceStatus,
    SQLiteSourceRegistry,
)


@dataclass
class Adapter:
    source_id: str = "test:source"
    calls: int = 0

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        self.calls += 1
        return AdapterResult(self.source_id, 1, ("evidence",), ("event",), ("hash",))

    def health(self):
        from ois.infrastructure.source_adapters.base import AdapterHealth

        return AdapterHealth(self.source_id, True, "now")


def build_fabric() -> SourceFabric:
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=ledger, outbox=ledger, idempotency=SQLiteIdempotencyStore())
    control = SourceControlAPI(SQLiteSourceRegistry())
    return SourceFabric(gateway=gateway, source_control=control)


def source(*, mode: str = "poll", enabled: bool = True) -> SourceDefinition:
    return SourceDefinition(
        source_id="test:source",
        tenant_id="t1",
        workspace_id="w1",
        provider="test",
        mode=mode,
        enabled=enabled,
        poll_interval_seconds=30,
        capabilities=("health_check", "incremental_sync"),
    )


def test_source_registration_requires_explicit_enablement() -> None:
    control = SourceControlAPI(SQLiteSourceRegistry())
    registered = control.register(source(enabled=False))

    assert registered.status == SourceStatus.REGISTERED
    assert not registered.enabled

    enabled = control.enable(tenant_id="t1", workspace_id="w1", source_id="test:source")
    assert enabled.status == SourceStatus.ENABLED
    assert enabled.enabled


def test_source_lifecycle_rejects_invalid_transition() -> None:
    control = SourceControlAPI(SQLiteSourceRegistry())
    control.register(source())

    with pytest.raises(ValueError, match="invalid source lifecycle transition"):
        control.pause(tenant_id="t1", workspace_id="w1", source_id="test:source")

    control.enable(tenant_id="t1", workspace_id="w1", source_id="test:source")
    paused = control.pause(tenant_id="t1", workspace_id="w1", source_id="test:source")
    assert paused.status == SourceStatus.PAUSED



def test_source_fabric_register_enable_and_poll() -> None:
    fabric = build_fabric()
    adapter = Adapter()

    registered = fabric.register(source(), adapter)
    assert registered.status == SourceStatus.REGISTERED

    fabric.enable(tenant_id="t1", workspace_id="w1", source_id="test:source")
    run = fabric.poll_once(tenant_id="t1", workspace_id="w1", source_id="test:source")

    assert run.error is None
    assert run.result is not None
    assert run.result.records == 1
    assert adapter.calls == 1
    assert fabric.health.get(
        tenant_id="t1", workspace_id="w1", source_id="test:source"
    ) is not None


def test_source_fabric_failure_degrades_and_success_recovers() -> None:
    class FlakyAdapter(Adapter):
        def ingest(self, **kwargs: object) -> AdapterResult:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("upstream unavailable")
            return AdapterResult(self.source_id, 1, ("e",), ("ev",), ("h",))

    fabric = build_fabric()
    adapter = FlakyAdapter()
    fabric.register(source(), adapter)
    fabric.enable(tenant_id="t1", workspace_id="w1", source_id="test:source")

    first = fabric.poll_once(tenant_id="t1", workspace_id="w1", source_id="test:source")
    assert first.error is not None
    assert fabric.source_control.get(
        tenant_id="t1", workspace_id="w1", source_id="test:source"
    ).status == SourceStatus.DEGRADED

    second = fabric.poll_with_retry(
        tenant_id="t1", workspace_id="w1", source_id="test:source"
    )
    assert second.error is None
    assert fabric._source_control.get(
        tenant_id="t1", workspace_id="w1", source_id="test:source"
    ).status == SourceStatus.ENABLED


def test_cursor_store_requires_expected_version() -> None:
    store = SQLiteCursorStore()
    first = store.advance("t1", "w1", "test:source", "page-1")
    second = store.advance(
        "t1",
        "w1",
        "test:source",
        "page-2",
        expected_version=first.version,
    )
    assert second.version == 2

    with pytest.raises(ValueError, match="version conflict"):
        store.advance(
            "t1",
            "w1",
            "test:source",
            "page-3",
            expected_version=first.version,
        )


def test_retry_controller_is_bounded_and_exponential() -> None:
    controller = RetryController(
        RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4, jitter_ratio=0),
    )

    first = controller.decide(attempt=1, retryable=True)
    second = controller.decide(attempt=2, retryable=True)
    final = controller.decide(attempt=3, retryable=True)

    assert first.retry and first.delay_seconds == 1
    assert second.retry and second.delay_seconds == 2
    assert not final.retry and final.delay_seconds == 0


def test_health_registry_tracks_consecutive_failures() -> None:
    registry = SourceHealthRegistry()
    first = registry.record(
        tenant_id="t1",
        workspace_id="w1",
        source_id="test:source",
        healthy=False,
        error="timeout",
    )
    second = registry.record(
        tenant_id="t1",
        workspace_id="w1",
        source_id="test:source",
        healthy=False,
        error="timeout",
    )
    recovered = registry.record(
        tenant_id="t1",
        workspace_id="w1",
        source_id="test:source",
        healthy=True,
    )

    assert first.consecutive_failures == 1
    assert second.consecutive_failures == 2
    assert recovered.consecutive_failures == 0
    assert recovered.state == "healthy"


def test_source_fabric_preserves_provenance_at_gateway_boundary() -> None:
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=ledger, outbox=ledger)
    control = SourceControlAPI(SQLiteSourceRegistry())
    fabric = SourceFabric(gateway=gateway, source_control=control)
    fabric.register(source(), Adapter())
    fabric.enable(tenant_id="t1", workspace_id="w1", source_id="test:source")

    result = fabric.ingest_observation(
        tenant_id="t1",
        workspace_id="w1",
        source_id="test:source",
        record_id="record-1",
        payload={"value": 1},
        provenance=SourceProvenance(
            provider="test",
            endpoint="https://example.invalid/api",
            operation="read",
            request_id="req-1",
            resource_id="record-1",
        ),
    )

    assert result.accepted
    event = ledger.pending()[0]
    assert event.payload["provenance"]["request_id"] == "req-1"


def test_webhook_registration_is_lifecycle_scoped() -> None:
    fabric = build_fabric()
    control = fabric.source_control
    control.register(source(mode="webhook"))

    with pytest.raises(PermissionError):
        fabric.register_webhook(
            tenant_id="t1",
            workspace_id="w1",
            source_id="test:source",
            gateway=WebhookGateway(
                gateway=SourceGateway(),
                security=WebhookSecurity(WebhookSecurityPolicy(secret=b"secret")),
            ),
        )


def test_source_definition_rejects_invalid_poll_interval() -> None:
    with pytest.raises(ValueError, match="poll_interval_seconds"):
        SourceDefinition(
            source_id="test:source",
            tenant_id="t1",
            workspace_id="w1",
            provider="test",
            mode="poll",
            poll_interval_seconds=0,
        )
