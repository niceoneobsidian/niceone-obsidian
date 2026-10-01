"""File and export source adapter with content hashing through Source Gateway."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .base import AdapterResult, SourceAdapterRegistry


class FileSourceAdapter:
    def __init__(self, *, source_id: str, path: str) -> None:
        self.source_id = source_id
        self._path = Path(path)

    def _read(self) -> Any:
        suffix = self._path.suffix.lower()
        if suffix == ".json":
            return json.loads(self._path.read_text(encoding="utf-8"))
        if suffix == ".csv":
            with self._path.open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
        return {
            "filename": self._path.name,
            "content": self._path.read_text(encoding="utf-8"),
        }

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        payload = self._read()
        response = gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=self.source_id,
                source_record_id=str(self._path.resolve()),
                payload={"path": str(self._path), "data": payload},
                connector_version="file-v1",
                schema_version="file.record.v1",
            )
        )
        return SourceAdapterRegistry.response(self.source_id, [response])
