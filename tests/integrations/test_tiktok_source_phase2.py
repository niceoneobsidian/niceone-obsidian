import json
from typing import Any, cast
from urllib.request import Request

import pytest

from ois.infrastructure.source_gateway import SourceGateway, SQLiteSourceLedger
from ois.integrations.tiktok.client import TikTokDisplayClient
from ois.integrations.tiktok.source import TikTokSource


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_tiktok_page_enters_gateway_before_cursor_advances() -> None:
    calls = []

    def opener(request: Request, timeout: float):
        calls.append(request)
        return FakeResponse(
            {
                "data": {"videos": [{"id": "123"}], "cursor": 1, "has_more": True},
                "error": {"code": "ok"},
            }
        )

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        evidence=cast(Any, ledger),
        outbox=cast(Any, ledger),
    )
    cursor: list[str | None] = [None]
    source = TikTokSource(
        client=TikTokDisplayClient("token", opener=opener, max_retries=0),
        gateway=gateway,
        get_cursor=lambda: cursor[0],
        advance_cursor=lambda value: cursor.__setitem__(0, value),
    )
    result = source.ingest_pages(
        tenant_id="tenant", workspace_id="workspace", credential_id="unused", max_pages=1
    )
    assert result.pages == 1
    assert result.videos == 1
    assert cursor[0] == "1"
    assert len(ledger.pending()) == 1
    assert ledger.pending()[0].event_type == "source.raw_evidence.created"
    assert calls[0].full_url.startswith("https://open.tiktokapis.com/v2/video/list/")


@pytest.mark.integration
def test_live_tiktok_display_source() -> None:
    """Opt-in proof against authorized live data.

    Required env: OIS_TIKTOK_ACCESS_TOKEN. This test intentionally does not
    print or persist the token. It validates the real API -> gateway -> ledger
    path. CI should keep it disabled unless the secret is provisioned.
    """
    import os

    token = os.getenv("OIS_TIKTOK_ACCESS_TOKEN")
    if not token:
        pytest.skip("OIS_TIKTOK_ACCESS_TOKEN not configured")
    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(evidence=cast(Any, ledger), outbox=cast(Any, ledger))
    cursor: list[str | None] = [None]
    source = TikTokSource(
        client=TikTokDisplayClient(token),
        gateway=gateway,
        get_cursor=lambda: cursor[0],
        advance_cursor=lambda value: cursor.__setitem__(0, value),
    )
    result = source.ingest_pages(
        tenant_id="live-test", workspace_id="live-test", credential_id="external", max_pages=1
    )
    assert result.pages == 1
    assert result.evidence_ids
    assert result.event_ids
    assert ledger.evidence(result.evidence_ids[0]) is not None
    assert ledger.pending()
