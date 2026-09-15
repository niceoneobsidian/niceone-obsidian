"""ChatGPT-backed live ingestion boundary for Social Intelligence.

This adapter treats structured observations supplied by ChatGPT as an external
observation source while platform APIs are being integrated. It deliberately
creates canonical SocialEvent records only; it does not publish, mutate remote
platforms, or infer business outcomes that were not supplied as evidence.

The same SocialEventStore and analytics contracts used by platform adapters are
used here, so this is a bridge to production ingestion rather than a second
pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Iterable

from .analytics_store import SQLiteAnalyticsStore
from .persistence import SocialEventStore
from .schemas import Evidence, SocialEvent


@dataclass(frozen=True)
class ChatObservation:
    """One observation explicitly supplied by ChatGPT from a source artifact."""

    platform: str
    event_type: str
    occurred_at: datetime
    text: str | None = None
    external_id: str | None = None
    author_id: str | None = None
    language: str | None = None
    metrics: dict[str, float] | None = None
    entities: tuple[str, ...] = ()
    source_id: str = "chatgpt"
    source_uri: str | None = None
    excerpt: str | None = None
    confidence: float = 0.7
    raw: dict[str, Any] | None = None


def _stable_external_id(observation: ChatObservation) -> str:
    """Create a deterministic ID when the upstream source has no native ID."""
    material = "|".join(
        (
            observation.platform,
            observation.event_type,
            observation.occurred_at.isoformat(),
            observation.text or "",
            observation.source_id,
            observation.source_uri or "",
        )
    )
    digest = sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"chatgpt:{digest}"


def normalize_observation(observation: ChatObservation) -> SocialEvent:
    """Convert a ChatGPT observation into the canonical SocialEvent contract."""
    external_id = observation.external_id or _stable_external_id(observation)
    evidence = Evidence(
        source_id=observation.source_id,
        uri=observation.source_uri,
        excerpt=observation.excerpt or observation.text,
        observed_at=datetime.now(UTC),
        confidence=observation.confidence,
    )
    return SocialEvent(
        platform=observation.platform,
        event_type=observation.event_type,
        occurred_at=observation.occurred_at,
        external_id=external_id,
        author_id=observation.author_id,
        text=observation.text,
        language=observation.language,
        metrics=dict(observation.metrics or {}),
        entities=list(observation.entities),
        evidence=[evidence],
        raw=dict(observation.raw or {}),
    )


def ingest_chat_observations(
    observations: Iterable[ChatObservation],
    event_store: SocialEventStore,
    analytics_store: SQLiteAnalyticsStore | None = None,
) -> tuple[list[SocialEvent], int, int]:
    """Ingest observations and optionally materialize supplied metrics.

    Returns (normalized_events, events_added, metrics_added). Existing events
    are deterministically deduplicated by the backing SocialEventStore.
    """
    events = [normalize_observation(item) for item in observations]

    # Preserve the append result for each event. Metrics must only be
    # materialized when the event was newly inserted, not when it is a
    # duplicate already known by the event store.
    append_results = [
        event_store.append(event)
        for event in events
    ]

    events_added = sum(append_results)
    metrics_added = 0

    if analytics_store is not None:
        for event, was_added in zip(events, append_results):
            if was_added:
                metrics_added += analytics_store.record_event_metrics(event)

    return events, events_added, metrics_added
