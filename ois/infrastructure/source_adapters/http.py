"""Generic authenticated HTTP source adapter using the standard library."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

from ois.infrastructure.source_gateway import (
    CredentialRef,
    SourceGateway,
    SourceRequest,
    TenantScope,
)
from ois.infrastructure.source_gateway.auth import (
    Authenticator,
    AuthRequest,
    AuthScheme,
)

from .base import AdapterHealth, AdapterResult, SourceAdapterRegistry, utc_now


class HttpSourceAdapter:
    def __init__(
        self,
        *,
        source_id: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
        timeout: float = 20.0,
        connector_version: str = "http-v1",
        auth_scheme: AuthScheme = AuthScheme.NONE,
        auth_options: dict[str, object] | None = None,
        authenticator: Authenticator | None = None,
    ) -> None:
        self.source_id = source_id
        self._url = url
        self._method = method.upper()
        self._headers = dict(headers or {})
        self._body = body
        self._timeout = timeout
        self._connector_version = connector_version
        self._auth_scheme = auth_scheme
        self._auth_options = dict(auth_options or {})
        self._authenticator = authenticator
        if self._authenticator is not None and self._auth_scheme is not AuthScheme.NONE:
            raise ValueError("choose auth_scheme or authenticator, not both")

    def _fetch(self, headers: dict[str, str] | None = None) -> object:
        payload = None
        request_headers = dict(headers or self._headers)
        if self._body is not None:
            payload = json.dumps(self._body).encode()
            request_headers.setdefault("Content-Type", "application/json")

        request = Request(
            self._url,
            data=payload,
            headers=request_headers,
            method=self._method,
        )
        with urlopen(request, timeout=self._timeout) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            return cast(object, json.loads(raw.decode("utf-8")))
        return raw.decode("utf-8")

    def health(self) -> AdapterHealth:
        try:
            self._fetch()
        except Exception as exc:
            return AdapterHealth(self.source_id, False, utc_now(), type(exc).__name__)
        return AdapterHealth(self.source_id, True, utc_now())

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        credential_ref: CredentialRef | None = None
        headers = dict(self._headers)
        payload_bytes = None
        if self._body is not None:
            payload_bytes = json.dumps(self._body).encode()
            headers.setdefault("Content-Type", "application/json")

        if self._auth_scheme is not AuthScheme.NONE or self._authenticator is not None:
            if credential_id is None:
                raise PermissionError("authentication credential required")
            credential_ref = CredentialRef(
                credential_id=credential_id,
                tenant_id=tenant_id,
                provider=self.source_id.split(":", 1)[0],
                scopes=(),
            )
            authenticated = gateway.authenticate_request(
                AuthRequest(self._method, self._url, headers, payload_bytes or b""),
                credential_ref,
                TenantScope(tenant_id=tenant_id, workspace_id=workspace_id),
                self._auth_scheme,
                options=self._auth_options,
                authenticator=self._authenticator,
            )
            headers = authenticated.headers

        payload = self._fetch(headers)
        response = gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=self.source_id,
                source_record_id=self._url,
                payload={"url": self._url, "response": payload},
                credential=credential_ref,
                connector_version=self._connector_version,
                schema_version="http.response.v1",
            )
        )
        return SourceAdapterRegistry.response(self.source_id, [response])
