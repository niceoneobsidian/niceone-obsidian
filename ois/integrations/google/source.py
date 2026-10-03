"""Google Drive source routed through the governed SourceGateway."""
from __future__ import annotations
from ois.infrastructure.source_adapters.http import HttpSourceAdapter
from ois.infrastructure.source_gateway import AuthScheme

class GoogleDriveSource(HttpSourceAdapter):
    source_id = "google.drive.files"
    def __init__(self, *, timeout: float = 20.0, page_size: int = 100) -> None:
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000")
        super().__init__(
            source_id=self.source_id,
            url="https://www.googleapis.com/drive/v3/files"
            f"?pageSize={page_size}&fields=nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
            timeout=timeout,
            connector_version="google-drive-v3",
            auth_scheme=AuthScheme.BEARER,
            headers={"Accept": "application/json"},
        )
