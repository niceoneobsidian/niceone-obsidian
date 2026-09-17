"""Canonical cross-platform measurement structures for Social Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class SocialMetric:
    platform: str
    content_id: str
    observed_at: str
    metrics: Mapping[str, float]
    source: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttributionRecord:
    conversion_id: str
    content_id: str
    campaign_id: str | None
    platform: str
    touchpoints: tuple[str, ...]
    value: float
    currency: str | None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PerformanceSummary:
    content_count: int
    totals: Mapping[str, float] = field(default_factory=dict)
    averages: Mapping[str, float] = field(default_factory=dict)


def summarize_metrics(records: list[SocialMetric]) -> PerformanceSummary:
    totals: dict[str, float] = {}
    for record in records:
        for key, value in record.metrics.items():
            totals[key] = totals.get(key, 0.0) + float(value)
    averages = {key: value / len(records) for key, value in totals.items()} if records else {}
    return PerformanceSummary(len(records), dict(sorted(totals.items())), dict(sorted(averages.items())))


def normalize_platform_metrics(platform: str, content_id: str, observed_at: str, metrics: Mapping[str, object], source: str, evidence_refs: tuple[str, ...] = ()) -> SocialMetric:
    """Normalize numeric provider metrics without inventing missing fields."""
    numeric = {str(k): float(v) for k, v in metrics.items() if isinstance(v, (int, float))}
    return SocialMetric(platform, content_id, observed_at, numeric, source, evidence_refs)
