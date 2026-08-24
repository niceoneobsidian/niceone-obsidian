"""Deterministic social-intelligence algorithms.

These functions intentionally have no side effects. Kernel execution, policy,
validation, memory and telemetry remain outside this domain layer.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Iterable

from .schemas import SocialEvent, SocialSignal

_TOKEN = re.compile(r"(?u)\b[\w#@'-]{2,}\b")
_POSITIVE = {"good", "great", "love", "best", "amazing", "excellent", "win", "happy"}
_NEGATIVE = {"bad", "hate", "worst", "awful", "terrible", "fail", "angry", "sad"}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def sentiment_score(text: str) -> float:
    """Small deterministic baseline; production models can replace it by contract."""
    tokens = tokenize(text)
    if not tokens:
        return 0.0
    pos = sum(t in _POSITIVE for t in tokens)
    neg = sum(t in _NEGATIVE for t in tokens)
    return max(-1.0, min(1.0, (pos - neg) / math.sqrt(len(tokens))))


def topic_counts(events: Iterable[SocialEvent], top_k: int = 10) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for event in events:
        counts.update(t for t in tokenize(event.text or "") if not t.startswith(("@", "#")))
    return counts.most_common(top_k)


def trend_velocity(events: Iterable[SocialEvent], bucket_seconds: int = 3600) -> dict[str, float]:
    """Return normalized growth from the previous time bucket to the latest bucket."""
    buckets: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for event in events:
        bucket = int(event.occurred_at.timestamp()) // bucket_seconds
        for token in set(tokenize(event.text or "")):
            buckets[token][bucket] += 1
    if not buckets:
        return {}
    latest = max(b for counts in buckets.values() for b in counts)
    previous = latest - 1
    result: dict[str, float] = {}
    for token, counts in buckets.items():
        now = counts[latest]
        before = counts[previous]
        result[token] = (now - before) / max(before, 1)
    return result


def detect_anomalies(values: list[float], z_threshold: float = 2.5) -> list[int]:
    if len(values) < 3:
        return []
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        return []
    return [i for i, value in enumerate(values) if abs(value - mean) / std >= z_threshold]


def engagement_rate(event: SocialEvent, denominator: float | None = None) -> float:
    metrics = event.metrics
    numerator = sum(float(metrics.get(k, 0)) for k in ("likes", "comments", "shares", "saves"))
    base = denominator if denominator is not None else float(metrics.get("impressions", metrics.get("reach", 0)))
    return numerator / base if base > 0 else 0.0


def signals_from_events(events: Iterable[SocialEvent]) -> list[SocialSignal]:
    materialized = list(events)
    signals: list[SocialSignal] = []
    for event in materialized:
        score = sentiment_score(event.text or "")
        signals.append(SocialSignal(
            signal_type="sentiment",
            value="positive" if score > 0.1 else "negative" if score < -0.1 else "neutral",
            score=min(1.0, abs(score)),
            platform=event.platform,
            confidence=0.5 if event.text else 0.2,
        ))
    for topic, count in topic_counts(materialized):
        signals.append(SocialSignal(
            signal_type="topic", value=topic,
            score=min(1.0, count / max(len(materialized), 1)),
            confidence=0.6,
        ))
    for topic, velocity in trend_velocity(materialized).items():
        if velocity > 0:
            signals.append(SocialSignal(
                signal_type="trend", value=topic,
                score=min(1.0, velocity / (1 + velocity)),
                velocity=velocity,
                confidence=0.5,
            ))
    return signals
