"""G1 ingestion pipeline: connector -> event -> intelligence -> research brief."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ois.domains.social_growth.connectors import ConnectorRegistry
from ois.domains.social_growth.persistence import SocialEventStore
from ois.domains.social_growth.schemas import SocialEvent, SocialResearchBrief
from ois.domains.social_growth.workflows import build_research_brief

from .source import SourceRegistry
from .store import IntelligenceStore


@dataclass(frozen=True)
class IngestionReport:
    """Outcome of one source ingestion and optional intelligence run."""

    source_id: str
    platform: str
    received: int
    accepted: int
    duplicates: int
    rejected: int
    errors: tuple[str, ...] = ()
    events: tuple[SocialEvent, ...] = ()
    research_brief_id: int | None = None
    research_brief: SocialResearchBrief | None = None


class IngestionPipeline:
    """Wire registered connectors, canonical event persistence and G1 intelligence."""

    def __init__(
        self,
        *,
        connectors: ConnectorRegistry,
        sources: SourceRegistry,
        event_store: SocialEventStore,
        intelligence_store: IntelligenceStore | None = None,
    ) -> None:
        self._connectors = connectors
        self._sources = sources
        self._event_store = event_store
        self._intelligence_store = intelligence_store

    def ingest(
        self,
        source_id: str,
        payloads: Iterable[Mapping[str, Any]],
        *,
        research_query: str | None = None,
    ) -> IngestionReport:
        source = self._sources.get(source_id)
        connector = self._connectors.get(source.platform)

        started = perf_counter()
        received = accepted = duplicates = rejected = 0
        errors: list[str] = []
        events: list[SocialEvent] = []

        for payload in payloads:
            received += 1
            try:
                event = connector.normalize_event(payload)
            except Exception as exc:  # noqa: BLE001 - malformed upstream payload
                rejected += 1
                errors.append(f"normalize_failed:{exc}")
                continue

            if not event.platform or not event.event_type or not event.occurred_at:
                rejected += 1
                errors.append(f"invalid_event:{event.event_id}")
                continue

            if self._event_store.append(event):
                accepted += 1
                events.append(event)
            else:
                duplicates += 1

        latency_ms = (perf_counter() - started) * 1000.0
        health_error = "all_events_rejected" if received and not accepted and not duplicates else None
        self._sources.record_health(
            source_id,
            error=health_error,
            events_ingested=accepted,
            latency_ms=latency_ms,
            metadata={"received": received, "duplicates": duplicates, "rejected": rejected},
        )

        brief: SocialResearchBrief | None = None
        brief_id: int | None = None
        if research_query is not None:
            if self._intelligence_store is None:
                raise RuntimeError("intelligence_store is required for research_query")
            brief = build_research_brief(research_query, events)
            brief_id = self._intelligence_store.put_research_brief(brief)

        return IngestionReport(
            source_id=source_id,
            platform=source.platform,
            received=received,
            accepted=accepted,
            duplicates=duplicates,
            rejected=rejected,
            errors=tuple(errors),
            events=tuple(events),
            research_brief_id=brief_id,
            research_brief=brief,
        )
