"""Provider-neutral football domain models inspired by sportsipy abstractions."""

from .analytics import records_to_dataframe, summarize_statistics
from .models import (
    FootballBoxscore,
    FootballFixture,
    FootballGame,
    FootballLeague,
    FootballPlayer,
    FootballSeason,
    FootballStanding,
    FootballStatistic,
    FootballTeam,
)
from .provider import DictFixtureRepository, FixtureRepository, FootballProvider
from .schedule import Schedule

__all__ = [
    "FootballTeam",
    "FootballLeague",
    "FootballSeason",
    "FootballFixture",
    "FootballGame",
    "FootballBoxscore",
    "FootballPlayer",
    "FootballStanding",
    "FootballStatistic",
    "Schedule",
    "FootballProvider",
    "FixtureRepository",
    "DictFixtureRepository",
    "records_to_dataframe",
    "summarize_statistics",
]
