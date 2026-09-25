"""DB-API compatible source adapter for incremental database extraction."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .base import AdapterResult, SourceAdapterRegistry


class DatabaseSourceAdapter:
    def __init__(
        self,
        *,
        source_id: str,
        connection_factory: Callable[[], Any],
        query: str,
        parameters_factory: Callable[[], tuple[Any, ...]] = lambda: (),
        record_id: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.source_id = source_id
        self._connection_factory = connection_factory
        self._query = query
        self._parameters_factory = parameters_factory
        self._record_id = record_id or (
            lambda row: str(row.get("id") or row.get("key") or hash(tuple(row.items())))
        )

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        connection = self._connection_factory()
        try:
            cursor = connection.cursor()
            cursor.execute(self._query, self._parameters_factory())
            columns = [item[0] for item in cursor.description or ()]
            responses = []
            for values in cursor.fetchall():
                row = dict(zip(columns, values, strict=False))
                responses.append(
                    gateway.ingest(
                        SourceRequest(
                            tenant_id=tenant_id,
                            workspace_id=workspace_id,
                            source_id=self.source_id,
                            source_record_id=self._record_id(row),
                            payload=row,
                            connector_version="database-v1",
                            schema_version="database.row.v1",
                        )
                    )
                )
            return SourceAdapterRegistry.response(self.source_id, responses)
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
