"""Deterministic Social Intelligence engines.

These engines transform canonical SocialEvent records into typed domain
intelligence. They have no external side effects; OIS owns routing, policy,
execution, validation, memory and observability.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt

from .algorithms import sentiment_score, tokenize, trend_velocity
from .schemas import AudienceProfile, CompetitorProfile, CreativePattern, SocialEvent, SocialSignal


@dataclass(frozen=True)
class DataQualityReport:
    accepted: int
    rejected: int
    issues: tuple[str, ...]


def validate_events(events: Iterable[SocialEvent]) -> DataQualityReport:
    accepted = rejected = 0
    issues: list[str] = []
    for event in events:
        if not event.platform or not event.event_type or not event.occurred_at:
            rejected += 1
            issues.append(f"invalid_event:{event.event_id}")
            continue
        accepted += 1
        if not event.external_id:
            issues.append(f"missing_external_id:{event.event_id}")
        if not event.evidence:
            issues.append(f"missing_evidence:{event.event_id}")
    return DataQualityReport(accepted, rejected, tuple(issues))


def resolve_entities(events: Iterable[SocialEvent]) -> dict[str, tuple[str, ...]]:
    """Build deterministic entity aliases from normalized event entity labels."""
    aliases: defaultdict[str, set[str]] = defaultdict(set)
    for event in events:
        for entity in event.entities:
            key = " ".join(tokenize(entity))
            if key:
                aliases[key].add(entity.strip())
    return {key: tuple(sorted(values)) for key, values in sorted(aliases.items())}


def cluster_topics(
    events: Iterable[SocialEvent], top_k: int = 20
) -> list[tuple[str, tuple[str, ...], int]]:
    """Group events by their strongest normalized lexical topic."""
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for event in events:
        tokens = [t for t in tokenize(event.text or "") if not t.startswith(("@", "#"))]
        if not tokens:
            continue
        topic = Counter(tokens).most_common(1)[0][0]
        groups[topic].append(event.event_id)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))[:top_k]
    return [(topic, tuple(ids), len(ids)) for topic, ids in ranked]


def detect_trends(events: Iterable[SocialEvent], min_velocity: float = 0.5) -> list[SocialSignal]:
    signals: list[SocialSignal] = []
    for topic, velocity in sorted(trend_velocity(events).items(), key=lambda item: -item[1]):
        if velocity < min_velocity:
            continue
        signals.append(
            SocialSignal(
                signal_type="trend",
                value=topic,
                score=min(1.0, velocity / (1.0 + velocity)),
                velocity=velocity,
                confidence=min(1.0, 0.4 + min(velocity, 2.0) * 0.2),
            )
        )
    return signals


def build_audience_profiles(events: Iterable[SocialEvent]) -> list[AudienceProfile]:
    by_platform: defaultdict[str, list[SocialEvent]] = defaultdict(list)
    for event in events:
        by_platform[event.platform].append(event)
    profiles: list[AudienceProfile] = []
    for platform, items in sorted(by_platform.items()):
        interests = Counter(
            t for e in items for t in tokenize(e.text or "") if not t.startswith(("@", "#"))
        )
        mean_sentiment = sum(sentiment_score(e.text or "") for e in items) / max(len(items), 1)
        profiles.append(
            AudienceProfile(
                audience_id=f"platform:{platform}",
                label=f"{platform} audience",
                interests=[term for term, _ in interests.most_common(10)],
                behaviors=[
                    "engaged" if sum(e.metrics.values()) > 0 else "observational" for e in items[:5]
                ],
                platforms=[platform],
                sentiment=mean_sentiment,
                confidence=min(1.0, 0.3 + sqrt(len(items)) / 10),
            )
        )
    return profiles


def build_competitor_profiles(events: Iterable[SocialEvent]) -> list[CompetitorProfile]:
    by_entity: defaultdict[str, list[SocialEvent]] = defaultdict(list)
    for event in events:
        for entity in event.entities:
            by_entity[entity].append(event)
    total = max(sum(len(items) for items in by_entity.values()), 1)
    profiles: list[CompetitorProfile] = []
    for name, items in sorted(by_entity.items()):
        voice = len(items) / total
        terms = Counter(
            t for e in items for t in tokenize(e.text or "") if not t.startswith(("@", "#"))
        )
        profiles.append(
            CompetitorProfile(
                competitor_id=f"entity:{name.lower().replace(' ', '-')}",
                name=name,
                share_of_voice=voice,
                strengths=[term for term, _ in terms.most_common(5)],
                gaps=[],
            )
        )
    return profiles


def extract_creative_patterns(events: Iterable[SocialEvent]) -> list[CreativePattern]:
    patterns: list[CreativePattern] = []
    for event in events:
        text = (event.text or "").strip()
        if not text:
            continue
        first_sentence = text.split(".", 1)[0][:120]
        patterns.append(
            CreativePattern(
                pattern_id=f"hook:{event.event_id}",
                pattern_type="hook",
                pattern=first_sentence,
                platform=event.platform,
                performance_score=float(event.metrics.get("engagement_rate", 0.0)),
                confidence=0.4 if event.evidence else 0.2,
                evidence=event.evidence,
            )
        )
    return patterns
