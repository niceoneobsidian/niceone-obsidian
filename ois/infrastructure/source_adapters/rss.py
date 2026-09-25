"""RSS/Atom source adapter."""

from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .base import AdapterHealth, AdapterResult, SourceAdapterRegistry, utc_now


class RSSSourceAdapter:
    def __init__(self, *, source_id: str, url: str, timeout: float = 20.0) -> None:
        self.source_id = source_id
        self._url = url
        self._timeout = timeout

    def _entries(self) -> list[dict[str, str]]:
        with urllib.request.urlopen(self._url, timeout=self._timeout) as response:
            root = ET.fromstring(response.read())
        entries = []
        for item in root.findall(".//item") + root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        ):
            def value(name: str) -> str:
                node = item.find(name)
                if node is None:
                    node = item.find(f"{{http://www.w3.org/2005/Atom}}{name}")
                return "" if node is None or node.text is None else node.text

            entries.append(
                {
                    "id": value("guid") or value("id") or value("link"),
                    "title": value("title"),
                    "link": value("link"),
                    "published": value("pubDate") or value("published"),
                    "summary": value("description") or value("summary"),
                }
            )
        return entries

    def health(self) -> AdapterHealth:
        try:
            self._entries()
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
        responses = [
            gateway.ingest(
                SourceRequest(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    source_id=self.source_id,
                    source_record_id=entry["id"],
                    payload=entry,
                    connector_version="rss-v1",
                    schema_version="rss.entry.v1",
                )
            )
            for entry in self._entries()
        ]
        return SourceAdapterRegistry.response(self.source_id, responses)
