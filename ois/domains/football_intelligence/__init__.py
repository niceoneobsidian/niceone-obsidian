"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, market-specific
probability engines, ensemble prediction, calibration and abstention primitives.
"""

from .ensemble import FootballEnsemble
from .feed_service import FootballFeedService, MatchFeatureSnapshot, ReconciledMatch
from .feeds import (
    APIFootballProvider,
    FeedConfigurationError,
    FeedError,
    FeedObservation,
    FeedResponseError,
    FootballFeedProvider,
    MatchFeed,
    PlayerStatFeed,
    SportmonksProvider,
    TeamStatFeed,
)
from .market_models import (
    CardMarketModel,
    CornerMarketModel,
    FootballMarketModelSuite,
    GoalMarketModel,
    LiveStateModel,
    MarketPrediction,
    MarketProbability,
    PlayerGoalModel,
    ResultMarketModel,
    ShotMarketModel,
)
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .statsbomb import StatsBombObservation, StatsBombOpenDataProvider

__all__ = [
    "APIFootballProvider",
    "CardMarketModel",
    "CornerMarketModel",
    "DixonColesModel",
    "EloModel",
    "FeedConfigurationError",
    "FeedError",
    "FeedObservation",
    "FeedResponseError",
    "FootballEnsemble",
    "FootballFeedProvider",
    "FootballFeedService",
    "FootballMarketModelSuite",
    "FootballPrediction",
    "GoalMarketModel",
    "LiveStateModel",
    "MatchFeed",
    "MatchFeatureSnapshot",
    "MatchState",
    "MarketPrediction",
    "MarketProbability",
    "PlayerGoalModel",
    "PlayerStatFeed",
    "PoissonModel",
    "ReconciledMatch",
    "ResultMarketModel",
    "ShotMarketModel",
    "SportmonksProvider",
    "StatsBombObservation",
    "StatsBombOpenDataProvider",
    "TeamSnapshot",
    "TeamStatFeed",
]
