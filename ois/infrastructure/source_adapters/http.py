"""Generic authenticated HTTP source adapter using the standard library."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

from ois.infrastructure.source_gateway import CredentialRef, SourceGateway, SourceRequest, TenantScope
from ois.infrastructure.source_gateway.auth import (
    AuthRequest,
    AuthScheme,
    CredentialMaterial,
    authenticator_for,
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

    def _fetch(self, credential: CredentialMaterial | None = None) -> object:
        payload = None
        headers = dict(self._headers)
        if self._body is not None:
            payload = json.dumps(self._body).encode()
            headers.setdefault("Content-Type", "application/json")
        if self._auth_scheme is not AuthScheme.NONE:
            if credential is None:
                raise PermissionError("authentication credential required")
            auth = authenticator_for(self._auth_scheme, **self._auth_options)
            authenticated = auth.apply(
                AuthRequest(self._method, self._url, headers, payload or b""),
                credential,
            )
            headers = authenticated.headers

        request = Request(
            self._url,
            data=payload,
            headers=headers,
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
        credential_material = None
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
        payload = self._fetch(credential_material)
        response = gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=self.source_id,
                source_record_id=self._url,
                payload={"url": self._url, "response": payload},
                credential=credential,
                connector_version=self._connector_version,
                schema_version="http.response.v1",
            )
        )
        return SourceAdapterRegistry.response(self.source_id, [response])
