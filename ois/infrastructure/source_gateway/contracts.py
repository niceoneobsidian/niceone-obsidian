"""Contracts for governed live-source integrations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class FreshnessPolicy:
    """Maximum age accepted for a source observation."""

    max_age_seconds: float

    def __post_init__(self) -> None:
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")

    def is_fresh(self, observed_at: datetime, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return current - observed_at <= timedelta(seconds=self.max_age_seconds)

    def expires_at(self, observed_at: datetime) -> datetime:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        return observed_at + timedelta(seconds=self.max_age_seconds)


@dataclass(frozen=True)
class SourceProvenance:
    """Stable provenance attached to a source observation."""

    provider: str
    endpoint: str
    operation: str
    request_id: str
    resource_id: str = ""
    cursor: str | None = None
    observed_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        observed = self.observed_at or datetime.now(UTC)
        return {
            "provider": self.provider,
            "endpoint": self.endpoint,
            "operation": self.operation,
            "request_id": self.request_id,
            "resource_id": self.resource_id,
            "cursor": self.cursor,
            "observed_at": observed.isoformat(),
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class SourceSpec:
    """Registry metadata describing a source without embedding provider secrets."""

    source_id: str
    provider: str
    protocol: str
    version: str = "v1"
    freshness: FreshnessPolicy | None = None
    capabilities: tuple[str, ...] = ()
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.source_id or not self.provider or not self.protocol:
            raise ValueError("source_id, provider, and protocol are required")
