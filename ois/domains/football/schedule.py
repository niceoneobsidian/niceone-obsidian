from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from .models import FootballFixture, FootballGame


class Schedule:
    """Iterable season/team schedule abstraction.

    Provider adapters populate fixtures; the domain layer stays independent of
    any upstream site or API and therefore avoids sportsipy's scraping coupling.
    """

    def __init__(self, fixtures: Iterable[FootballFixture] = ()) -> None:
        self._fixtures = tuple(fixtures)

    def __iter__(self) -> Iterator[FootballFixture]:
        return iter(self._fixtures)

    def __len__(self) -> int:
        return len(self._fixtures)

    def games(self) -> tuple[FootballGame, ...]:
        return tuple(f for f in self._fixtures if isinstance(f, FootballGame))

    def between(self, start: datetime, end: datetime) -> Schedule:
        return Schedule(
            f for f in self._fixtures if start <= f.kickoff <= end
        )

    def for_team(self, team_id: str) -> Schedule:
        return Schedule(
            f
            for f in self._fixtures
            if f.home_team_id == team_id or f.away_team_id == team_id
        )
