"""Sportmonks Football API v3 adapter backed by the governed Source Gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ois.infrastructure.source_gateway import (
    FreshnessPolicy,
    SourceGateway,
    SourceSpec,
)

from .base import AdapterHealth, AdapterResult, SourceAdapterRegistry
from .http import HttpSourceAdapter

SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"


@dataclass(frozen=True)
class SportmonksQuery:
    endpoint: str = "fixtures/latest"
    includes: tuple[str, ...] = ("participants", "scores", "state")

    def __post_init__(self) -> None:
        if not self.endpoint or self.endpoint.startswith("http"):
            raise ValueError("endpoint must be a relative Sportmonks API path")


class SportmonksFootballAdapter:
    source_id = "sportmonks:football:v3"
    provider = "sportmonks"
    protocol = "rest"

    def __init__(
        self,
        *,
        query: SportmonksQuery | None = None,
        freshness: FreshnessPolicy | None = None,
        timeout: float = 20.0,
        opener: Callable[..., object] | None = None,
    ) -> None:
        self.query = query or SportmonksQuery()
        self.freshness = freshness or FreshnessPolicy(30)
        self._http = HttpSourceAdapter(
            source_id=self.source_id,
            url=f"{SPORTMONKS_BASE_URL}/{self.query.endpoint.lstrip('/')}",
            method="GET",
            query={"include": ";".join(self.query.includes)},
            timeout=timeout,
            connector_version="sportmonks-v3",
            auth_scheme="api_key",
            auth_header="Authorization",
            freshness=self.freshness,
            opener=opener,
        )

    def spec(self) -> SourceSpec:
        return SourceSpec(
            source_id=self.source_id,
            provider=self.provider,
            protocol=self.protocol,
            version="v3",
            freshness=self.freshness,
            capabilities=("football.live", "football.fixtures", "evidence.raw"),
        )

    def health(
        self,
        *,
        gateway: SourceGateway | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        credential_id: str | None = None,
    ) -> AdapterHealth:
        return self._http.health(
            gateway=gateway,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
        )

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str,
    ) -> AdapterResult:
        if not credential_id:
            raise ValueError("Sportmonks requires a credential reference")
        return self._http.ingest(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            gateway=gateway,
            credential_id=credential_id,
        )

    @staticmethod
    def register(
        registry: SourceAdapterRegistry, **kwargs: Any
    ) -> SportmonksFootballAdapter:
        adapter = SportmonksFootballAdapter(**kwargs)
        registry.register(adapter, adapter.spec())
        return adapter
