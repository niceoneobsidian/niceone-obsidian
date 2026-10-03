from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from ois.infrastructure.source_adapters import PollPage, PollingEngine, PollingJob, PollingSourceAdapter
from ois.infrastructure.source_adapters.webhook_gateway import WebhookGateway, WebhookRequest
from ois.infrastructure.source_gateway import (
    RateLimitManager,
    RateLimitPolicy,
    SQLiteIdempotencyStore,
    SQLiteSourceLedger,
    SourceEvent,
    SourceGateway,
    SourceRequest,
    WebhookSecurity,
    WebhookSecurityPolicy,
)
from ois.infrastructure.source_registry import (
    SQLiteSourceRegistry,
    SourceControlAPI,
    SourceDefinition,
)


def gateway(**kwargs: object) -> SourceGateway:
    ledger = SQLiteSourceLedger()
    return SourceGateway(evidence=ledger, outbox=ledger, **kwargs)


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


def test_rate_limit_manager_is_enforced_by_gateway() -> None:
    limits = RateLimitManager({"t1:w1:source": RateLimitPolicy(1, 0.01)})
    ledger = SQLiteSourceLedger()
    g = SourceGateway(evidence=ledger, outbox=ledger, rate_limit_manager=limits)

    first = g.ingest(
        SourceRequest(
            tenant_id="t1", workspace_id="w1", source_id="source",
            source_record_id="1", payload={"id": 1},
        )
    )
    second = g.ingest(
        SourceRequest(
            tenant_id="t1", workspace_id="w1", source_id="source",
            source_record_id="2", payload={"id": 2},
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
        payload=body, signature=f"sha256={digest}", timestamp=timestamp,
        replay_key="delivery-1", tenant_id="t1", workspace_id="w1",
    )
    assert not security.verify(
        payload=body, signature=f"sha256={digest}", timestamp=timestamp,
        replay_key="delivery-1", tenant_id="t1", workspace_id="w1",
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
            tenant_id="t1", workspace_id="w1", source_id="github:webhook",
            record_id="evt-1", body=body, signature=f"sha256={digest}",
            timestamp=timestamp, idempotency_key="delivery-1",
        )
    )
    assert result.records == 1


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
