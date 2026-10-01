"""GitHub REST source adapter.

The adapter intentionally uses the standard library so GitHub remains an
ordinary governed source rather than a privileged runtime dependency.
"""

from __future__ import annotations

import json
from typing import cast
from urllib.request import Request, urlopen

from ois.infrastructure.source_gateway import CredentialRef, SourceGateway, SourceRequest

from .base import AdapterHealth, AdapterResult, SourceAdapterRegistry, utc_now


class GitHubSourceAdapter:
    def __init__(
        self,
        *,
        repository: str,
        resource: str = "commits",
        token: str | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.repository = repository
        self.resource = resource.strip("/")
        self.source_id = f"github:{self.resource}"
        self._token = token
        self._timeout = timeout

    @property
    def url(self) -> str:
        return f"https://api.github.com/repos/{self.repository}/{self.resource}"

    def _fetch(self) -> list[object] | dict[str, object]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OIS-SourceGateway/1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        request = Request(self.url, headers=headers)
        with urlopen(request, timeout=self._timeout) as response:
            return cast(
                list[object] | dict[str, object],
                json.loads(response.read().decode("utf-8")),
            )

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
        records = payload if isinstance(payload, list) else [payload]
        credential: CredentialRef | None = None
        if credential_id:
            credential = CredentialRef(
                credential_id=credential_id,
                tenant_id=tenant_id,
                provider="github",
                scopes=("read",),
            )
        responses = [
            gateway.ingest(
                SourceRequest(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=self.source_id,
                    source_record_id=(
                        str(item.get("sha") or item.get("id") or index)
                        if isinstance(item, dict)
                        else str(index)
                    ),
                    payload=(
                        cast(dict[str, object], item) if isinstance(item, dict) else {"value": item}
                    ),
                    credential=credential,
                    connector_version="github-rest-v1",
                    schema_version="github.resource.v1",
                )
            )
            for index, item in enumerate(records)
        ]
        return SourceAdapterRegistry.response(self.source_id, responses)
