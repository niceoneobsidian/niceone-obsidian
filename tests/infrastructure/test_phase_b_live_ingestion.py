from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from ois.infrastructure.source_adapters import (
    FileSourceAdapter,
    PollingEngine,
    PollingJob,
    PollingSourceAdapter,
    PollPage,
)
from ois.infrastructure.source_adapters.webhook_gateway import WebhookGateway, WebhookRequest
from ois.infrastructure.source_gateway import (
    RateLimitManager,
    RateLimitPolicy,
    SourceEvent,
    SourceGateway,
    SourceRequest,
    SQLiteIdempotencyStore,
    SQLiteSourceLedger,
    WebhookSecurity,
    WebhookSecurityPolicy,
)
from ois.infrastructure.source_gateway.socket import ApiSourceSocket
from ois.infrastructure.source_registry import (
    SourceControlAPI,
    SourceDefinition,
    SQLiteSourceRegistry,
)


def gateway(
    *,
    idempotency: SQLiteIdempotencyStore | None = None,
    rate_limit_manager: RateLimitManager | None = None,
) -> SourceGateway:
    ledger = SQLiteSourceLedger()
    return SourceGateway(
        evidence=ledger,
        outbox=ledger,
        idempotency=idempotency,
        rate_limit_manager=rate_limit_manager,
    )


def test_source_gateway_package_imports_cleanly() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from ois.infrastructure.source_gateway import SourceGateway; "
            "assert SourceGateway.__name__ == 'SourceGateway'",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_canonical_source_event_is_stable() -> None:
    first = SourceEvent.from_payload(
        tenant_id="t1",
        workspace_id="w1",
        source_id="github:repo",
        source_record_id="42",
        payload={"b": 2, "a": 1},
    )
    second = SourceEvent.from_payload(
        tenant_id="t1",
        workspace_id="w1",
        source_id="github:repo",
        source_record_id="42",
        payload={"a": 1, "b": 2},
    )
    assert first.event_id == second.event_id
    assert first.payload_hash == second.payload_hash


def test_gateway_preserves_durable_raw_evidence_event_type() -> None:
    ledger = SQLiteSourceLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger)

    result = g.ingest(
        SourceRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="github:repo",
            source_record_id="42",
            payload={"id": 42},
        )
    )

    assert result.accepted
    pending = ledger.pending()
    assert len(pending) == 1
    assert pending[0].event_type == "source.raw_evidence.created"
    assert pending[0].payload["event_type"] == "source.observation"


def test_gateway_deduplicates_explicit_idempotency_key() -> None:
    store = SQLiteIdempotencyStore()
    ledger = SQLiteSourceLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger, idempotency=store)

    first = g.ingest(
        SourceRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="github:repo",
            source_record_id="42",
            payload={"id": 42},
            idempotency_key="delivery-42",
        )
    )
    second = g.ingest(
        SourceRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="github:repo",
            source_record_id="different",
            payload={"id": 43},
            idempotency_key="delivery-42",
        )
    )
    assert first.accepted
    assert not second.accepted
    assert second.reason == "duplicate_idempotency"


def test_concurrent_delivery_key_accepts_only_one_observation() -> None:
    store = SQLiteIdempotencyStore()
    ledger = SQLiteSourceLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger, idempotency=store)
    request = SourceRequest(
        tenant_id="t1",
        workspace_id="w1",
        source_id="github:repo",
        source_record_id="42",
        payload={"id": 42},
        idempotency_key="delivery-concurrent",
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        responses = tuple(executor.map(g.ingest, (request,) * 8))

    assert sum(response.accepted for response in responses) == 1
    assert sum(response.reason == "duplicate_idempotency" for response in responses) == 7
    assert len(ledger.pending()) == 1


def test_failed_durable_acceptance_releases_idempotency_claim() -> None:
    class FailingLedger:
        def commit_ingest(self, evidence: object, event: object) -> bool:
            raise RuntimeError("simulated persistence failure")

    store = SQLiteIdempotencyStore()
    ledger = FailingLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger, idempotency=store)
    request = SourceRequest(
        tenant_id="t1",
        workspace_id="w1",
        source_id="github:repo",
        source_record_id="42",
        payload={"id": 42},
        idempotency_key="delivery-42",
    )

    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        g.ingest(request)

    assert store.get(tenant_id="t1", workspace_id="w1", key="delivery-42") is None


def test_rate_limit_manager_is_enforced_by_gateway() -> None:
    limits = RateLimitManager({"t1:w1:source": RateLimitPolicy(1, 0.01)})
    ledger = SQLiteSourceLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger, rate_limit_manager=limits)

    first = g.ingest(
        SourceRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="source",
            source_record_id="1",
            payload={"id": 1},
        )
    )
    second = g.ingest(
        SourceRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="source",
            source_record_id="2",
            payload={"id": 2},
        )
    )
    assert first.accepted
    assert not second.accepted
    assert second.reason == "rate_limited"


def test_webhook_security_is_timestamp_bound_and_replay_resistant() -> None:
    secret = b"test-secret"
    now = 1_700_000_000.0
    timestamp = str(int(now))
    body = json.dumps({"id": "evt-1", "type": "push"}).encode()
    digest = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    security = WebhookSecurity(
        WebhookSecurityPolicy(secret=secret),
        replay_store=SQLiteIdempotencyStore(),
        clock=lambda: now,
    )
    assert security.verify(
        payload=body,
        signature=f"sha256={digest}",
        timestamp=timestamp,
        replay_key="delivery-1",
        tenant_id="t1",
        workspace_id="w1",
    )
    assert not security.verify(
        payload=body,
        signature=f"sha256={digest}",
        timestamp=timestamp,
        replay_key="delivery-1",
        tenant_id="t1",
        workspace_id="w1",
    )


def test_webhook_gateway_routes_verified_json() -> None:
    secret = b"test-secret"
    now = 1_700_000_000.0
    timestamp = str(int(now))
    body = json.dumps({"id": "evt-1", "type": "push"}).encode()
    digest = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    security = WebhookSecurity(
        WebhookSecurityPolicy(secret=secret),
        replay_store=SQLiteIdempotencyStore(),
        clock=lambda: now,
    )
    result = WebhookGateway(
        gateway=gateway(idempotency=SQLiteIdempotencyStore()),
        security=security,
    ).receive(
        WebhookRequest(
            tenant_id="t1",
            workspace_id="w1",
            source_id="github:webhook",
            record_id="evt-1",
            body=body,
            signature=f"sha256={digest}",
            timestamp=timestamp,
            idempotency_key="delivery-1",
        )
    )
    assert result.records == 1


def test_webhook_replay_reservation_is_released_on_ingest_failure() -> None:
    secret = b"test-secret"
    now = 1_700_000_000.0
    timestamp = str(int(now))
    body = json.dumps({"id": "evt-1", "type": "push"}).encode()
    digest = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    replay_store = SQLiteIdempotencyStore()
    security = WebhookSecurity(
        WebhookSecurityPolicy(secret=secret),
        replay_store=replay_store,
        clock=lambda: now,
    )

    class FailingGateway:
        def ingest(self, request: object) -> object:
            raise RuntimeError("simulated persistence failure")

    webhook = WebhookGateway(gateway=FailingGateway(), security=security)

    request = WebhookRequest(
        tenant_id="t1",
        workspace_id="w1",
        source_id="github:webhook",
        record_id="evt-1",
        body=body,
        signature=f"sha256={digest}",
        timestamp=timestamp,
        idempotency_key="delivery-failure",
    )
    with pytest.raises(RuntimeError, match="simulated persistence failure"):
        webhook.receive(request)

    assert security.verify(
        payload=body,
        signature=f"sha256={digest}",
        timestamp=timestamp,
        replay_key="delivery-failure",
        tenant_id="t1",
        workspace_id="w1",
    )


def test_source_control_is_tenant_scoped() -> None:
    api = SourceControlAPI(SQLiteSourceRegistry())
    source = api.register(
        SourceDefinition(
            source_id="github:repo",
            tenant_id="t1",
            workspace_id="w1",
            provider="github",
            mode="poll",
        )
    )
    assert source.enabled
    assert api.list(tenant_id="t1", workspace_id="w1") == (source,)
    with pytest.raises(KeyError):
        api.get(tenant_id="t2", workspace_id="w1", source_id="github:repo")


def test_socket_blocks_disabled_registered_source(tmp_path) -> None:
    path = tmp_path / "source.json"
    path.write_text('{"id":"1","value":"live"}', encoding="utf-8")

    registry = SourceControlAPI(SQLiteSourceRegistry())
    api_socket = ApiSourceSocket(
        gateway=gateway(),
        source_control=registry,
    )
    api_socket.register(FileSourceAdapter(source_id="file:test", path=str(path)))
    api_socket.register_definition(
        SourceDefinition(
            source_id="file:test",
            tenant_id="t1",
            workspace_id="w1",
            provider="file",
            mode="poll",
        )
    )
    registry.set_enabled(
        tenant_id="t1",
        workspace_id="w1",
        source_id="file:test",
        enabled=False,
    )

    with pytest.raises(PermissionError, match="source is disabled"):
        api_socket.ingest("file:test", tenant_id="t1", workspace_id="w1")


def test_polling_engine_schedules_existing_polling_adapter() -> None:
    cursor: str | None = None
    records = [{"id": "1", "value": "a"}]

    def fetch(value: str | None) -> PollPage:
        return PollPage(tuple(records) if value is None else (), "done")

    def get_cursor() -> str | None:
        return cursor

    def set_cursor(value: str | None) -> None:
        nonlocal cursor
        cursor = value

    adapter = PollingSourceAdapter(
        source_id="poll:source",
        fetch_page=fetch,
        get_cursor=get_cursor,
        set_cursor=set_cursor,
    )
    engine = PollingEngine(
        gateway=gateway(),
        jobs=(
            PollingJob(
                source_id="poll:source",
                interval_seconds=60,
                adapter=adapter,
                tenant_id="t1",
                workspace_id="w1",
            ),
        ),
    )
    run = engine.run_once("poll:source")
    assert run.error is None
    assert run.result is not None
    assert run.result.records == 1
    assert cursor == "done"


def test_polling_engine_run_due_supports_sqlite_gateway_from_worker_thread() -> None:
    cursor: str | None = None

    def fetch(value: str | None) -> PollPage:
        return PollPage(({"id": "1", "value": "a"},) if value is None else (), "done")

    def get_cursor() -> str | None:
        return cursor

    def set_cursor(value: str | None) -> None:
        nonlocal cursor
        cursor = value

    adapter = PollingSourceAdapter(
        source_id="poll:threaded",
        fetch_page=fetch,
        get_cursor=get_cursor,
        set_cursor=set_cursor,
    )
    engine = PollingEngine(
        gateway=gateway(),
        jobs=(
            PollingJob(
                source_id="poll:threaded",
                interval_seconds=60,
                adapter=adapter,
                tenant_id="t1",
                workspace_id="w1",
            ),
        ),
    )

    runs = engine.run_due()

    assert len(runs) == 1
    assert runs[0].error is None
    assert runs[0].result is not None
    assert runs[0].result.records == 1
    assert cursor == "done"
