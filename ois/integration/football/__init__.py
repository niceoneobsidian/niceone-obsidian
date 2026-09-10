"""Provider-neutral football data integrations for OIS."""

from ois.integration.football.clients import ApiFootballClient, SportmonksClient
from ois.integration.football.features import PlayerFeatureVector, build_player_features
from ois.integration.football.gateway import FootballDataGateway, FootballDataProvider
from ois.integration.football.models import (
    FootballFixture,
    FootballPlayer,
    PlayerMatchStat,
    PlayerSeasonStat,
    TeamMatchStat,
)

__all__ = [
    "ApiFootballClient",
    "FootballDataGateway",
    "FootballDataProvider",
    "FootballFixture",
    "FootballPlayer",
    "PlayerFeatureVector",
    "PlayerMatchStat",
    "PlayerSeasonStat",
    "SportmonksClient",
    "TeamMatchStat",
    "build_player_features",
]
