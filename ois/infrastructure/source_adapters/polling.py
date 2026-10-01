"""Incremental polling adapter with checkpoint-after-commit semantics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .base import AdapterResult, SourceAdapterRegistry


@dataclass(frozen=True)
class PollPage:
    records: tuple[dict[str, Any], ...]
    next_cursor: str | None


class PollingSourceAdapter:
    def __init__(
        self,
        *,
        source_id: str,
        fetch_page: Callable[[str | None], PollPage],
        get_cursor: Callable[[], str | None],
        set_cursor: Callable[[str | None], None],
        max_pages: int = 10,
        connector_version: str = "poll-v1",
    ) -> None:
        self.source_id = source_id
        self._fetch_page = fetch_page
        self._get_cursor = get_cursor
        self._set_cursor = set_cursor
        self._max_pages = max_pages
        self._connector_version = connector_version

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        gateway: SourceGateway,
        credential_id: str | None = None,
    ) -> AdapterResult:
        cursor = self._get_cursor()
        responses = []
        for _ in range(self._max_pages):
            page = self._fetch_page(cursor)
            for record in page.records:
                response = gateway.ingest(
                    SourceRequest(
                        tenant_id=tenant_id,
                        workspace_id=workspace_id,
                        source_id=self.source_id,
                        source_record_id=str(record.get("id", cursor or "page")),
                        payload=record,
                        connector_version=self._connector_version,
                        schema_version="poll.record.v1",
                    )
                )
                if not response.accepted and response.reason != "duplicate_evidence":
                    raise RuntimeError(
                        f"source gateway rejected {self.source_id}: {response.reason}"
                    )
                responses.append(response)
            self._set_cursor(page.next_cursor)
            cursor = page.next_cursor
            if cursor is None:
                break
        return SourceAdapterRegistry.response(self.source_id, responses)
