"""Multi-provider football feed orchestration.

The service deliberately does not choose a betting market or place a wager. It
collects, normalizes and reconciles evidence for downstream prediction models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from .feeds import FootballFeedProvider, MatchFeed, PlayerStatFeed, TeamStatFeed


@dataclass(frozen=True)
class ReconciledMatch:
    """Cross-provider match view with explicit source precedence."""

    match: MatchFeed
    sources: tuple[str, ...]


@dataclass(frozen=True)
class MatchFeatureSnapshot:
    """Prediction-time feature bundle assembled from provider observations."""

    match: ReconciledMatch
    team_statistics: tuple[TeamStatFeed, ...]
    player_statistics: tuple[PlayerStatFeed, ...]
    observed_at: datetime


class FootballFeedService:
    """Coordinate provider adapters without coupling the model to any vendor."""

    def __init__(self, providers: Iterable[FootballFeedProvider]) -> None:
        self.providers = tuple(providers)
        if not self.providers:
            raise ValueError("At least one football feed provider is required")

    def live_matches(self) -> tuple[ReconciledMatch, ...]:
        """Collect live matches and deduplicate them by normalized team identity."""
        matches: dict[tuple[str, str], ReconciledMatch] = {}
        for provider in self.providers:
            for match in provider.live_matches():
                key = _match_key(match)
                existing = matches.get(key)
                if existing is None:
                    matches[key] = ReconciledMatch(match=match, sources=(provider.provider_name,))
                else:
                    matches[key] = ReconciledMatch(
                        match=existing.match,
                        sources=existing.sources + (provider.provider_name,),
                    )
        return tuple(sorted(matches.values(), key=lambda item: (item.match.competition, item.match.home_team)))

    def feature_snapshot(self, match: ReconciledMatch) -> MatchFeatureSnapshot:
        """Fetch team/player evidence using the provider that produced the match."""
        provider = next(
            provider for provider in self.providers if provider.provider_name == match.match.provider
        )
        team_stats = provider.match_statistics(match.match.provider_match_id)
        player_stats = provider.player_statistics(match.match.provider_match_id)
        return MatchFeatureSnapshot(
            match=match,
            team_statistics=team_stats,
            player_statistics=player_stats,
            observed_at=datetime.now(UTC),
        )


def _match_key(match: MatchFeed) -> tuple[str, str]:
    """Use normalized team names as the cross-provider fallback identity."""
    return (
        _normalize_name(match.home_team),
        _normalize_name(match.away_team),
    )


def _normalize_name(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())
