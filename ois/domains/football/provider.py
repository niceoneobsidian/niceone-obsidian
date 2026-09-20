from __future__ import annotations

from collections.abc import Iterable, Mapping, Protocol

from .models import FootballBoxscore, FootballFixture, FootballLeague, FootballStanding, FootballTeam
from .schedule import Schedule


class FootballProvider(Protocol):
    """Provider-neutral contract for API-Football, Sportmonks, TheSportsDB, etc."""

    provider_name: str

    def teams(self, league_id: str, season_id: str) -> Iterable[FootballTeam]: ...

    def schedule(self, team_id: str, season_id: str) -> Schedule: ...

    def boxscore(self, fixture_id: str) -> FootballBoxscore: ...

    def standings(self, league_id: str, season_id: str) -> Iterable[FootballStanding]: ...


class FixtureRepository(Protocol):
    """Local fixture/test-data boundary, modeled after sportsipy's local page concept."""

    def load(self, name: str) -> Mapping[str, object]: ...


class DictFixtureRepository:
    def __init__(self, fixtures: Mapping[str, Mapping[str, object]]) -> None:
        self._fixtures = dict(fixtures)

    def load(self, name: str) -> Mapping[str, object]:
        try:
            return self._fixtures[name]
        except KeyError as exc:
            raise KeyError(f"Fixture not found: {name}") from exc
