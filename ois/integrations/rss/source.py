"""RSS/news -> OIS Source Gateway adapter.

This adapter treats a public RSS feed as a production external source. It
never persists credentials and writes each fetched feed document through the
same Raw Evidence + Outbox path used by authenticated social connectors.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest


@dataclass(frozen=True)
class RSSItem:
    item_id: str
    title: str
    uri: str | None
    published_at: datetime | None
    description: str | None

    def as_payload(self) -> dict[str, object]:
        topics = [self.title] if self.title else []
        return {
            "id": self.item_id,
            "title": self.title,
            "uri": self.uri,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "description": self.description,
            "topics": topics,
        }


@dataclass(frozen=True)
class RSSSourceRun:
    source_id: str
    items: int
    evidence_ids: tuple[str, ...]
    event_ids: tuple[str, ...]


class RSSSource:
    """Fetch one RSS feed and commit each item through Source Gateway."""

    def __init__(
        self,
        *,
        feed_url: str,
        gateway: SourceGateway,
        source_id: str = "rss.news",
        user_agent: str = "Niceone-Obsidian/1.0",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.feed_url = feed_url
        self.source_id = source_id
        self._gateway = gateway
        self._user_agent = user_agent
        self._timeout = timeout_seconds

    def fetch(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        max_items: int = 50,
        topic: str | None = None,
    ) -> RSSSourceRun:
        if max_items < 1:
            raise ValueError("max_items must be positive")

        request = Request(
            self.feed_url,
            headers={"User-Agent": self._user_agent},
        )
        with urlopen(request, timeout=self._timeout) as response:
            body = response.read()

        root = ElementTree.fromstring(body)
        items = _parse_items(root)[:max_items]
        evidence_ids: list[str] = []
        event_ids: list[str] = []

        for item in items:
            payload = item.as_payload()
            if topic:
                payload["topics"] = [topic]
                payload["research_topic"] = topic
            result = self._gateway.ingest(
                SourceRequest(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=self.source_id,
                    source_record_id=item.item_id,
                    payload=payload,
                    connector_version="rss-xml",
                    schema_version="rss.item.v1",
                )
            )
            if not result.accepted and result.reason == "duplicate_evidence":
                continue
            if not result.accepted:
                raise RuntimeError(
                    f"gateway rejected RSS item {item.item_id}: {result.reason}"
                )
            evidence_ids.append(result.evidence_id)
            event_ids.append(result.event_id)

        return RSSSourceRun(
            source_id=self.source_id,
            items=len(items),
            evidence_ids=tuple(evidence_ids),
            event_ids=tuple(event_ids),
        )


def _parse_items(root: ElementTree.Element) -> list[RSSItem]:
    items = root.findall(".//item")
    parsed: list[RSSItem] = []
    for index, item in enumerate(items):
        title = _text(item.find("title")) or ""
        uri = _text(item.find("link"))
        item_id = _text(item.find("guid")) or uri or f"rss-item-{index}"
        description = _text(item.find("description"))
        published_at = _parse_date(_text(item.find("pubDate")))
        parsed.append(RSSItem(item_id, title, uri, published_at, description))
    return parsed


def _text(element: ElementTree.Element | None) -> str | None:
    if element is None:
        return None
    value = "".join(element.itertext()).strip()
    return value or None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    return parsed.astimezone(UTC)
