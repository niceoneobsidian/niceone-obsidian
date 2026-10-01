"""Generic authenticated HTTP source adapter using the standard library."""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

from ois.infrastructure.source_gateway import CredentialRef, SourceGateway, SourceRequest

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
    ) -> None:
        self.source_id = source_id
        self._url = url
        self._method = method.upper()
        self._headers = dict(headers or {})
        self._body = body
        self._timeout = timeout
        self._connector_version = connector_version

    def _fetch(self) -> object:
        payload = None
        headers = dict(self._headers)
        if self._body is not None:
            payload = json.dumps(self._body).encode()
            headers.setdefault("Content-Type", "application/json")
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
        payload = self._fetch()
        credential: CredentialRef | None = None
        if credential_id:
            credential = CredentialRef(
                credential_id=credential_id,
                tenant_id=tenant_id,
                provider=self.source_id.split(":", 1)[0],
                scopes=(),
            )
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
