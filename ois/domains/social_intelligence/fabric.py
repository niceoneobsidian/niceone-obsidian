"""Canonical Social Intelligence Fabric runtime primitives.

External systems are reference implementations only. OIS owns the canonical
contracts, state, provenance, policy boundary, and execution lifecycle.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Iterable, Mapping, Protocol


@dataclass(frozen=True)
class EvidenceRef:
    source: str
    uri: str | None = None
    captured_at: str = ""
    fingerprint: str = ""

    @classmethod
    def from_payload(cls, source: str, payload: Mapping[str, Any], uri: str | None = None) -> "EvidenceRef":
        encoded = repr(sorted((str(k), repr(v)) for k, v in payload.items())).encode()
        return cls(source=source, uri=uri, captured_at=datetime.now(UTC).isoformat(), fingerprint=sha256(encoded).hexdigest())


@dataclass(frozen=True)
class SocialEvent:
    event_id: str
    platform: str
    event_type: str
    occurred_at: str
    actor_id: str | None = None
    content_id: str | None = None
    text: str = ""
    entities: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    engagement: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[EvidenceRef, ...] = ()

    @classmethod
    def from_payload(cls, platform: str, payload: Mapping[str, Any]) -> "SocialEvent":
        raw_id = str(payload.get("id") or payload.get("uri") or sha256(repr(sorted(payload.items())).encode()).hexdigest())
        occurred = str(payload.get("occurred_at") or payload.get("created_at") or datetime.now(UTC).isoformat())
        entities = tuple(str(x) for x in payload.get("entities", ()) if x is not None)
        topics = tuple(str(x).lower() for x in payload.get("topics", ()) if x is not None)
        engagement = {str(k): float(v) for k, v in dict(payload.get("engagement", {})).items() if isinstance(v, (int, float))}
        evidence = tuple(payload.get("evidence", ()))
        if not evidence:
            evidence = (EvidenceRef.from_payload(platform, payload, str(payload.get("url")) if payload.get("url") else None),)
        return cls(
            event_id=f"{platform}:{raw_id}",
            platform=platform,
            event_type=str(payload.get("event_type") or "post"),
            occurred_at=occurred,
            actor_id=str(payload["actor_id"]) if payload.get("actor_id") is not None else None,
            content_id=str(payload["content_id"]) if payload.get("content_id") is not None else None,
            text=str(payload.get("text") or payload.get("content") or ""),
            entities=entities,
            topics=topics,
            engagement=engagement,
            metadata=dict(payload.get("metadata", {})),
            evidence=evidence,
        )


@dataclass(frozen=True)
class SocialSignal:
    signal_id: str
    signal_type: str
    value: str
    score: float
    confidence: float
    source_event_ids: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass(frozen=True)
class Trend:
    topic: str
    score: float
    velocity: float
    event_count: int
    event_ids: tuple[str, ...]


class SocialSource(Protocol):
    source_id: str
    def collect(self, query: str = "") -> Iterable[Mapping[str, Any]]: ...


class SocialSourceRegistry:
    """Deterministic registry for read-side social sources."""

    def __init__(self) -> None:
        self._sources: dict[str, SocialSource] = {}

    def register(self, source: SocialSource) -> None:
        if source.source_id in self._sources:
            raise ValueError(f"Duplicate social source: {source.source_id}")
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> SocialSource:
        return self._sources[source_id]

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._sources))


class InMemorySocialEventStore:
    """Append-only event store suitable for deterministic tests and local runtime."""

    def __init__(self) -> None:
        self._events: dict[str, SocialEvent] = {}

    def append(self, event: SocialEvent) -> bool:
        if event.event_id in self._events:
            return False
        self._events[event.event_id] = event
        return True

    def list(self) -> tuple[SocialEvent, ...]:
        return tuple(self._events[key] for key in sorted(self._events))

    def by_platform(self, platform: str) -> tuple[SocialEvent, ...]:
        return tuple(event for event in self.list() if event.platform == platform)


def normalize_events(platform: str, payloads: Iterable[Mapping[str, Any]]) -> tuple[SocialEvent, ...]:
    return tuple(SocialEvent.from_payload(platform, payload) for payload in payloads)


def detect_trends(events: Iterable[SocialEvent], *, min_count: int = 2) -> tuple[Trend, ...]:
    grouped: dict[str, list[SocialEvent]] = defaultdict(list)
    for event in events:
        for topic in event.topics:
            grouped[topic].append(event)
    total = max(sum(len(items) for items in grouped.values()), 1)
    trends: list[Trend] = []
    for topic, items in grouped.items():
        if len(items) < min_count:
            continue
        timestamps = sorted(item.occurred_at for item in items)
        velocity = len(items) / max(1, len(set(timestamps)))
        score = min(1.0, (len(items) / total) * 0.7 + min(velocity / 10.0, 0.3))
        trends.append(Trend(topic=topic, score=score, velocity=velocity, event_count=len(items), event_ids=tuple(item.event_id for item in items)))
    return tuple(sorted(trends, key=lambda item: (-item.score, item.topic)))


def build_signals(events: Iterable[SocialEvent]) -> tuple[SocialSignal, ...]:
    materialized = tuple(events)
    topic_events: dict[str, list[SocialEvent]] = defaultdict(list)
    for event in materialized:
        for topic in event.topics:
            topic_events[topic].append(event)
    total = max(len(materialized), 1)
    signals = []
    for topic, items in sorted(topic_events.items()):
        score = min(1.0, len(items) / total)
        evidence = tuple(ref for event in items for ref in event.evidence)
        signals.append(SocialSignal(
            signal_id=f"topic:{topic}", signal_type="topic", value=topic,
            score=score, confidence=min(1.0, 0.4 + 0.1 * len(items)),
            source_event_ids=tuple(event.event_id for event in items), evidence=evidence,
        ))
    return tuple(signals)


def aggregate_engagement(events: Iterable[SocialEvent]) -> Mapping[str, float]:
    totals: Counter[str] = Counter()
    for event in events:
        for key, value in event.engagement.items():
            totals[key] += value
    return dict(sorted(totals.items()))
