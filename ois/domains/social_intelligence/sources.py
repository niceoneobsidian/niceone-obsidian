"""Streaming/read-side adapters inspired by open social protocols.

The adapter is deliberately provider-neutral. A real Bluesky/ATProto or
Mastodon implementation can feed the same canonical event boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .fabric import SocialEvent, SocialSourceRegistry


@dataclass(frozen=True)
class EventBatch:
    source: str
    events: tuple[SocialEvent, ...]


class PayloadSource:
    def __init__(self, source_id: str, payloads: Iterable[Mapping[str, Any]]) -> None:
        self.source_id = source_id
        self._payloads = tuple(payloads)

    def collect(self, query: str = "") -> Iterable[Mapping[str, Any]]:
        del query
        return self._payloads


def collect_source(registry: SocialSourceRegistry, source_id: str, *, query: str = "") -> EventBatch:
    source = registry.get(source_id)
    events = tuple(SocialEvent.from_payload(source_id, payload) for payload in source.collect(query))
    return EventBatch(source=source_id, events=events)


def register_reference_stream_sources(registry: SocialSourceRegistry) -> None:
    """Register source identities; network access remains an external Tool concern."""
    for source_id in ("bluesky", "mastodon", "x", "reddit", "youtube", "web"):
        registry.register(PayloadSource(source_id, ()))
