"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration and abstention primitives. Platform registration remains owned by OIS.
"""

from .ensemble import FootballEnsemble
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .statistics_client import (
    StatisticsClientError,
    api_football_fixture,
    api_football_match_statistics,
    api_football_player_statistics,
    sportmonks_fixture,
)
from .statistics_features import (
    PlayerFeatureVector,
    TeamFeatureVector,
    player_features,
    player_market_features,
    team_features,
)
from .statistics_sources import (
    MatchFeed,
    MatchStatistics,
    PlayerMatchStatistics,
    parse_api_football_fixture,
    parse_api_football_players,
    parse_api_football_statistics,
    parse_sportmonks_fixture,
)

__all__ = [
    "DixonColesModel",
    "EloModel",
    "FootballEnsemble",
    "FootballPrediction",
    "MatchFeed",
    "MatchState",
    "MatchStatistics",
    "PlayerFeatureVector",
    "PlayerMatchStatistics",
    "PoissonModel",
    "StatisticsClientError",
    "TeamFeatureVector",
    "TeamSnapshot",
    "api_football_fixture",
    "api_football_match_statistics",
    "api_football_player_statistics",
    "parse_api_football_fixture",
    "parse_api_football_players",
    "parse_api_football_statistics",
    "parse_sportmonks_fixture",
    "player_features",
    "player_market_features",
    "sportmonks_fixture",
    "team_features",
]
