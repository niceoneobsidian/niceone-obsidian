"""Deterministic attribution primitives for Social Growth."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AttributionTouchpoint:
    touchpoint_id: str
    entity_id: str
    event_type: str
    occurred_at: datetime
    value: float = 0.0


@dataclass(frozen=True)
class AttributionResult:
    conversion_id: str
    credited_touchpoints: tuple[tuple[str, float], ...]
    total_value: float
    confidence: float


def linear_attribution(
    conversion_id: str,
    touchpoints: Iterable[AttributionTouchpoint],
    conversion_value: float,
) -> AttributionResult:
    """Split conversion value equally across observed touchpoints."""
    ordered = tuple(touchpoints)
    if not ordered:
        return AttributionResult(conversion_id, (), 0.0, 0.0)
    share = conversion_value / len(ordered)
    return AttributionResult(
        conversion_id=conversion_id,
        credited_touchpoints=tuple((tp.touchpoint_id, share) for tp in ordered),
        total_value=conversion_value,
        confidence=min(1.0, 0.5 + 0.1 * len(ordered)),
    )
