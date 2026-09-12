"""Provider-neutral football domain models inspired by sportsipy abstractions."""

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
from .analytics import records_to_dataframe, summarize_statistics

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
    "records_to_dataframe",
    "summarize_statistics",
]
