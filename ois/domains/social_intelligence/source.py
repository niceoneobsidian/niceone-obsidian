"""G1 source registry and observable source-health primitives.

The registry is deliberately side-effect free: deployment-owned connectors and
schedulers report observations into it. Persistence belongs to the deployment
layer, while the contract remains deterministic and thread-safe for local use.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import Enum
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceStatus(str, Enum):
    """Observed reliability state of a registered source."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    STALE = "stale"


class SocialSource(BaseModel):
    """Stable identity and configuration metadata for an intelligence source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    platform: str
    kind: str = "connector"
    description: str = ""
    enabled: bool = True
    tags: tuple[str, ...] = ()
    stale_after_seconds: int = Field(default=3600, ge=1)


class SourceHealthSample(BaseModel):
    """One observed health reading for a source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    status: SourceStatus
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: float | None = Field(default=None, ge=0)
    error: str | None = None
    events_ingested: int = Field(default=0, ge=0)
    metadata: Mapping[str, Any] = Field(default_factory=dict)


def _classify(*, error: str | None, events_ingested: int) -> SourceStatus:
    if error is not None:
        return SourceStatus.DOWN
    if events_ingested == 0:
        return SourceStatus.DEGRADED
    return SourceStatus.HEALTHY


class SourceRegistry:
    """Register sources and retain a bounded, observable health history."""

    def __init__(self, *, history_limit: int = 50) -> None:
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")
        self._sources: dict[str, SocialSource] = {}
        self._history: dict[str, list[SourceHealthSample]] = {}
        self._history_limit = history_limit
        self._lock = RLock()

    def register(self, source: SocialSource) -> None:
        with self._lock:
            if source.source_id in self._sources:
                raise ValueError(f"source already registered: {source.source_id}")
            self._sources[source.source_id] = source
            self._history[source.source_id] = []

    def get(self, source_id: str) -> SocialSource:
        with self._lock:
            try:
                return self._sources[source_id]
            except KeyError as exc:
                raise KeyError(f"unknown source: {source_id}") from exc

    def list(self, *, enabled_only: bool = False) -> tuple[SocialSource, ...]:
        with self._lock:
            sources = tuple(self._sources.values())
        if enabled_only:
            sources = tuple(source for source in sources if source.enabled)
        return tuple(sorted(sources, key=lambda source: source.source_id))

    def record_health(
        self,
        source_id: str,
        *,
        error: str | None = None,
        events_ingested: int = 0,
        latency_ms: float | None = None,
        metadata: Mapping[str, Any] | None = None,
        observed_at: datetime | None = None,
    ) -> SourceHealthSample:
        with self._lock:
            if source_id not in self._sources:
                raise KeyError(f"unknown source: {source_id}")
            sample = SourceHealthSample(
                source_id=source_id,
                status=_classify(error=error, events_ingested=events_ingested),
                observed_at=observed_at or datetime.now(UTC),
                latency_ms=latency_ms,
                error=error,
                events_ingested=events_ingested,
                metadata=dict(metadata or {}),
            )
            history = self._history[source_id]
            history.append(sample)
            del history[: max(0, len(history) - self._history_limit)]
            return sample

    def health(self, source_id: str, *, now: datetime | None = None) -> SourceHealthSample | None:
        with self._lock:
            source = self.get(source_id)
            history = self._history[source_id]
            sample = history[-1] if history else None
        if sample is None:
            return None
        current = now or datetime.now(UTC)
        if current - sample.observed_at > timedelta(seconds=source.stale_after_seconds):
            return sample.model_copy(update={"status": SourceStatus.STALE})
        return sample

    def history(self, source_id: str) -> tuple[SourceHealthSample, ...]:
        with self._lock:
            if source_id not in self._sources:
                raise KeyError(f"unknown source: {source_id}")
            return tuple(self._history[source_id])

    def status(self, source_id: str, *, now: datetime | None = None) -> SourceStatus:
        sample = self.health(source_id, now=now)
        return SourceStatus.UNKNOWN if sample is None else sample.status

    def unhealthy(self, *, now: datetime | None = None) -> tuple[str, ...]:
        with self._lock:
            source_ids = tuple(sorted(self._sources))
        return tuple(
            source_id
            for source_id in source_ids
            if self.status(source_id, now=now)
            in (SourceStatus.DOWN, SourceStatus.DEGRADED, SourceStatus.STALE)
        )
