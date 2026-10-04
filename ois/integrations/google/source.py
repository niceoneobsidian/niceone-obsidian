"""Google Drive source routed through the governed SourceGateway."""

from __future__ import annotations

from urllib.parse import quote

from ois.infrastructure.source_adapters.base import AdapterResult, SourceAdapterRegistry
from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_gateway import (
    AuthScheme,
    CredentialRef,
    SourceGateway,
    SourceRequest,
    TenantScope,
)
from ois.infrastructure.source_gateway.gateway import SourceResponse


class GoogleDriveSource(HttpSourceAdapter):
    source_id = "google.drive.files"

    def __init__(self, *, timeout: float = 20.0, page_size: int = 100) -> None:
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000")
        self._page_size = page_size
        super().__init__(
            source_id=self.source_id,
            url="https://www.googleapis.com/drive/v3/files"
            f"?pageSize={page_size}&fields=nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
            timeout=timeout,
            connector_version="google-drive-v3",
            auth_scheme=AuthScheme.BEARER,
            headers={"Accept": "application/json"},
        )

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
                provider="google",
                scopes=(),
            )
            credential_material = gateway.resolve_credential(
                credential_ref,
                TenantScope(tenant_id=tenant_id, workspace_id=workspace_id),
            )

        responses: list[SourceResponse] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            url = self._url_for_page(page_token)
            fetch_result = self._fetch(credential_material, url=url)
            payload = fetch_result[0] if isinstance(fetch_result, tuple) else fetch_result
            response = gateway.ingest(
                SourceRequest(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=self.source_id,
                    source_record_id=url,
                    payload={"url": url, "response": payload},
                    credential=credential_ref,
                    connector_version=self._connector_version,
                    schema_version="google.drive.files.v1",
                )
            )
            responses.append(response)

            if not isinstance(payload, dict):
                break
            next_token = payload.get("nextPageToken")
            if not next_token:
                break
            token = str(next_token)
            if token in seen_tokens:
                raise RuntimeError("Google Drive pagination returned a repeated nextPageToken")
            seen_tokens.add(token)
            page_token = token

        return SourceAdapterRegistry.response(self.source_id, responses)

    def _url_for_page(self, page_token: str | None) -> str:
        if page_token is None:
            return self._url
        return f"{self._url}&pageToken={quote(page_token, safe='')}"
