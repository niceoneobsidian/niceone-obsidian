"""TikTok -> OIS Source Gateway adapter.

The adapter never persists access tokens. Each successful API page is handed to
the Phase 1 gateway as immutable raw evidence; the source cursor advances only
after the gateway confirms the evidence + outbox write.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .client import TikTokDisplayClient, TikTokPage


@dataclass(frozen=True)
class TikTokSourceRun:
    pages: int
    videos: int
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    final_cursor: str | None


class TikTokSource:
    source_id = "tiktok.display.v2"

    def __init__(
        self,
        *,
        client: TikTokDisplayClient,
        gateway: SourceGateway,
        get_cursor: Callable[[], str | None],
        advance_cursor: Callable[[str], None],
    ) -> None:
        self._client = client
        self._gateway = gateway
        self._get_cursor = get_cursor
        self._advance_cursor = advance_cursor

    def ingest_pages(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        credential_id: str,
        max_pages: int = 1,
        max_count: int = 20,
    ) -> TikTokSourceRun:
        if max_pages < 1:
            raise ValueError("max_pages must be positive")
        cursor = self._get_cursor()
        pages = 0
        videos = 0
        evidence_ids: list[str] = []
        event_ids: list[str] = []

        while pages < max_pages:
            page: TikTokPage = self._client.list_videos(cursor=cursor, max_count=max_count)
            source_record_id = f"cursor:{cursor or 'initial'}"
            result = self._gateway.ingest(
                SourceRequest(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=self.source_id,
                    source_record_id=source_record_id,
                    payload=page.raw,
                    credential=None,
                    connector_version="tiktok-display-v2",
                    schema_version="tiktok.display.v2",
                )
            )
            if not result.accepted and result.reason == "rate_limited":
                break
            if not result.accepted and result.reason == "duplicate_evidence":
                if not page.has_more:
                    break
            elif not result.accepted:
                raise RuntimeError(f"gateway rejected TikTok page: {result.reason}")

            evidence_ids.append(result.evidence_id)
            event_ids.append(result.event_id)
            pages += 1
            videos += len(page.videos)

            if not page.has_more or page.cursor is None:
                cursor = None
                break
            cursor = page.cursor
            self._advance_cursor(cursor)

        return TikTokSourceRun(pages, videos, tuple(evidence_ids), tuple(event_ids), cursor)
