"""Generic authenticated HTTP/REST source adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Callable, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from ois.infrastructure.source_gateway import (
    Authenticator,
    AuthRequest,
    AuthScheme,
    CredentialMaterial,
    CredentialRef,
    FreshnessPolicy,
    SourceGateway,
    SourceProvenance,
    SourceRequest,
    TenantScope,
    authenticator_for,
)

from .base import AdapterHealth, AdapterResult, SourceAdapterRegistry, utc_now


class HttpSourceAdapter:
    """Governed generic REST adapter.

    Provider I/O happens here; authentication, tenant scope, rate limiting,
    evidence and outbox persistence remain governed by the Source Gateway.
    """

    def __init__(
        self,
        *,
        source_id: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        query: dict[str, str | int | float] | None = None,
        body: dict[str, object] | None = None,
        timeout: float = 20.0,
        connector_version: str = "http-v2",
        auth_scheme: AuthScheme = AuthScheme.NONE,
        auth_options: dict[str, object] | None = None,
        authenticator: Authenticator | None = None,
        freshness: FreshnessPolicy | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("HTTP source URL must use http:// or https://")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise ValueError("unsupported HTTP method")
        if authenticator is not None and auth_scheme is not AuthScheme.NONE:
            raise ValueError("choose auth_scheme or authenticator, not both")
        self.source_id = source_id
        self._url = url
        self._method = method.upper()
        self._headers = dict(headers or {})
        self._query = dict(query or {})
        self._body = body
        self._timeout = timeout
        self._connector_version = connector_version
        self._auth_scheme = auth_scheme
        self._auth_options = dict(auth_options or {})
        self._authenticator = authenticator
        self._freshness = freshness
        self._opener = opener or urlopen
        self._last_observed_at: datetime | None = None

    def _request_url(self) -> str:
        if not self._query:
            return self._url
        separator = "&" if "?" in self._url else "?"
        return f"{self._url}{separator}{urlencode(self._query)}"

    def _fetch(
        self,
        credential: CredentialMaterial | None = None,
    ) -> tuple[object, str, float]:
        request_url = self._request_url()
        payload = None
        headers = dict(self._headers)
        if self._body is not None:
            payload = json.dumps(self._body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        if self._auth_scheme is not AuthScheme.NONE or self._authenticator is not None:
            if credential is None:
                raise PermissionError("authentication credential required")
            auth = self._authenticator or authenticator_for(
                self._auth_scheme, **self._auth_options
            )
            authenticated = auth.apply(
                AuthRequest(self._method, request_url, headers, payload or b""),
                credential,
            )
            headers = authenticated.headers

        request = Request(
            request_url,
            data=payload,
            headers=headers,
            method=self._method,
        )
        started = monotonic()
        with self._opener(request, timeout=self._timeout) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            status = str(getattr(response, "status", 200))
        elapsed_ms = (monotonic() - started) * 1000
        if "json" in content_type.lower():
            return cast(object, json.loads(raw.decode("utf-8"))), status, elapsed_ms
        return raw.decode("utf-8"), status, elapsed_ms

    def health(
        self,
        *,
        gateway: SourceGateway | None = None,
        tenant_id: str | None = None,
        workspace_id: str | None = None,
        credential_id: str | None = None,
    ) -> AdapterHealth:
        started = monotonic()
        try:
            credential = None
            if credential_id:
                if gateway is None or tenant_id is None or workspace_id is None:
                    raise ValueError(
                        "gateway and tenant/workspace are required for credentialed health checks"
                    )
                credential = gateway.resolve_credential(
                    CredentialRef(
                        credential_id=credential_id,
                        tenant_id=tenant_id,
                        provider=self.source_id.split(":", 1)[0],
                    ),
                    TenantScope(tenant_id=tenant_id, workspace_id=workspace_id),
                )
            self._fetch(credential)
            self._last_observed_at = datetime.now(UTC)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, PermissionError) as exc:
            return AdapterHealth(
                self.source_id,
                False,
                utc_now(),
                (monotonic() - started) * 1000,
                False,
                type(exc).__name__,
            )
        return AdapterHealth(
            self.source_id,
            True,
            utc_now(),
            (monotonic() - started) * 1000,
            self._freshness_ok(),
        )

    def _freshness_ok(self) -> bool | None:
        if self._freshness is None or self._last_observed_at is None:
            return None
        return self._freshness.is_fresh(self._last_observed_at)

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        credential_ref: CredentialRef | None = None
        credential_material: CredentialMaterial | None = None
        if credential_id:
            credential_ref = CredentialRef(
                credential_id=credential_id,
                tenant_id=tenant_id,
                provider=self.source_id.split(":", 1)[0],
                scopes=(),
            )
            credential_material = gateway.resolve_credential(
                credential_ref,
                TenantScope(tenant_id=tenant_id, workspace_id=workspace_id),
            )

        source_type = self.source_id.split(":", 1)[0]
        lease = None
        if gateway.rate_limit_configured(
            source_type=source_type,
            source_id=self.source_id,
        ):
            lease = gateway.acquire_rate_limit(
                source_type=source_type,
                source_id=self.source_id,
            )
            if lease is None:
                return SourceAdapterRegistry.response(self.source_id, [])

        payload, status, _latency = self._fetch(credential_material)
        observed_at = datetime.now(UTC)
        self._last_observed_at = observed_at
        if self._freshness and not self._freshness.is_fresh(observed_at):
            raise RuntimeError(f"source response is stale: {self.source_id}")

        provenance = SourceProvenance(
            provider=source_type,
            endpoint=self._request_url(),
            operation=self._method,
            request_id=str(uuid4()),
            resource_id=self._url,
            observed_at=observed_at,
            metadata={"http_status": status},
        )
        response = gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_type=source_type,
                source_id=self.source_id,
                source_record_id=self._url,
                payload={"url": self._url, "response": payload},
                credential=credential_ref,
                connector_version=self._connector_version,
                schema_version="http.response.v1",
                provenance=provenance,
                observed_at=observed_at,
                rate_limit_lease=lease,
            )
        )
        return SourceAdapterRegistry.response(self.source_id, [response])
