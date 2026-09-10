"""Provider-agnostic football data gateway for Market Intelligence."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from ois.integration.football.models import (
    FootballFixture,
    PlayerMatchStat,
    PlayerSeasonStat,
)


class FootballDataProvider(Protocol):
    """Minimum provider contract required by the intelligence layer."""

    provider: str

    def fixtures_by_date(self, day: date) -> list[FootballFixture]: ...

    def fixture(self, fixture_id: str) -> FootballFixture: ...

    def player_match_stats(self, fixture_id: str) -> list[PlayerMatchStat]: ...

    def player_season_stats(
        self, player_id: str, season_id: str | int
    ) -> list[PlayerSeasonStat]: ...


class FootballDataGateway:
    """Route reads to one or more providers without leaking provider semantics."""

    def __init__(self, providers: list[FootballDataProvider]) -> None:
        if not providers:
            raise ValueError("at least one football data provider is required")
        self._providers = providers

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(provider.provider for provider in self._providers)

    def fixtures_by_date(self, day: date) -> list[FootballFixture]:
        fixtures: dict[tuple[str, str, str], FootballFixture] = {}
        for provider in self._providers:
            for fixture in provider.fixtures_by_date(day):
                key = (
                    fixture.starting_at.isoformat(),
                    fixture.home_team_name.casefold(),
                    fixture.away_team_name.casefold(),
                )
                fixtures.setdefault(key, fixture)
        return sorted(fixtures.values(), key=lambda fixture: fixture.starting_at)

    def fixture(self, fixture_id: str, provider: str | None = None) -> FootballFixture:
        for candidate in self._providers:
            if provider is not None and candidate.provider != provider:
                continue
            try:
                return candidate.fixture(fixture_id)
            except Exception:
                continue
        raise LookupError(f"fixture {fixture_id!r} was not found in configured providers")

    def player_match_stats(
        self, fixture_id: str, provider: str | None = None
    ) -> list[PlayerMatchStat]:
        for candidate in self._providers:
            if provider is not None and candidate.provider != provider:
                continue
            try:
                return candidate.player_match_stats(fixture_id)
            except Exception:
                continue
        raise LookupError(f"player statistics for fixture {fixture_id!r} are unavailable")

    def player_season_stats(
        self, player_id: str, season_id: str | int, provider: str | None = None
    ) -> list[PlayerSeasonStat]:
        for candidate in self._providers:
            if provider is not None and candidate.provider != provider:
                continue
            try:
                return candidate.player_season_stats(player_id, season_id)
            except Exception:
                continue
        raise LookupError(
            f"season statistics for player {player_id!r} are unavailable"
        )
