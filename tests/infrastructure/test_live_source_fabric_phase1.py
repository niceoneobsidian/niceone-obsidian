from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.message import Message
from urllib.request import Request

import pytest

from ois.infrastructure.source_adapters import HttpSourceAdapter, SourceAdapterRegistry
from ois.infrastructure.source_gateway import AuthScheme
from ois.infrastructure.source_gateway import (
    FreshnessPolicy,
    InMemoryCredentialResolver,
    RateLimitPolicy,
    SourceGateway,
    SourceProvenance,
    SourceSpec,
    SQLiteSourceLedger,
)


class FakeResponse:
    def __init__(
        self,
        payload: object,
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_registry_stores_explicit_source_contract() -> None:
    registry = SourceAdapterRegistry()
    adapter = HttpSourceAdapter(source_id="example:api", url="https://example.test/data")
    spec = SourceSpec(
        source_id="example:api",
        provider="example",
        protocol="rest",
        capabilities=("read",),
        freshness=FreshnessPolicy(60),
    )
    registry.register(adapter, spec)
    assert registry.list() == ("example:api",)
    assert registry.spec("example:api") == spec


def test_http_adapter_applies_bearer_credential_and_persists_provenance() -> None:
    calls: list[dict[str, str]] = []

    def opener(request: Request, *, timeout: float) -> FakeResponse:
        headers = request.headers
        calls.append({"authorization": headers["Authorization"], "timeout": str(timeout)})
        return FakeResponse({"id": "42", "value": "live"})

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        credentials=InMemoryCredentialResolver({"cred-1": "secret-token"}),
        evidence=ledger,
        outbox=ledger,
    )
    adapter = HttpSourceAdapter(
        source_id="example:api",
        url="https://example.test/data",
        auth_scheme=AuthScheme.BEARER,
        freshness=FreshnessPolicy(60),
        opener=opener,
    )

    result = adapter.ingest(
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        gateway=gateway,
        credential_id="cred-1",
    )

    assert result.records == 1
    assert calls == [{"authorization": "Bearer secret-token", "timeout": "20.0"}]
    evidence = ledger.evidence(result.evidence_ids[0])
    assert evidence is not None
    assert evidence.payload["response"]["value"] == "live"

    pending = ledger.pending()
    assert len(pending) == 1
    assert pending[0].payload["provenance"]["provider"] == "example"
    assert pending[0].payload["provenance"]["endpoint"] == "https://example.test/data"


def test_http_adapter_does_not_call_provider_when_rate_limited() -> None:
    calls = 0

    def opener(request: object, *, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse({"ok": True})

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        evidence=ledger,
        outbox=ledger,
        rate_limits={"example": RateLimitPolicy(1, 0.001)},
    )
    adapter = HttpSourceAdapter(
        source_id="example:api",
        url="https://example.test/data",
        opener=opener,
    )

    first = adapter.ingest(
        tenant_id="tenant-a", workspace_id="workspace-a", gateway=gateway
    )
    second = adapter.ingest(
        tenant_id="tenant-a", workspace_id="workspace-a", gateway=gateway
    )

    assert first.records == 1
    assert second.records == 0
    assert calls == 1


def test_http_adapter_requires_credentials_for_authenticated_source() -> None:
    adapter = HttpSourceAdapter(
        source_id="example:api",
        url="https://example.test/data",
        auth_scheme="api_key",
        opener=lambda request, timeout: FakeResponse({"ok": True}),
    )
    gateway = SourceGateway(
        credentials=InMemoryCredentialResolver({"cred": "key"}),
        evidence=SQLiteSourceLedger(),
        outbox=SQLiteSourceLedger(),
    )
    with pytest.raises(PermissionError):
        adapter.ingest(
            tenant_id="tenant-a",
            workspace_id="workspace-a",
            gateway=gateway,
        )


def test_provenance_contract_is_serializable() -> None:
    observed = datetime.now(UTC)
    provenance = SourceProvenance(
        provider="example",
        endpoint="https://example.test/data",
        operation="GET",
        request_id="req-1",
        observed_at=observed,
        metadata={"status": 200},
    )
    data = provenance.as_dict()
    assert data["request_id"] == "req-1"
    assert data["observed_at"] == observed.isoformat()


def test_freshness_policy_rejects_stale_observation() -> None:
    policy = FreshnessPolicy(30)
    stale = datetime.now(UTC) - timedelta(seconds=31)
    assert not policy.is_fresh(stale)
