"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration and abstention primitives. Platform registration remains owned by OIS.
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
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .statsbomb import StatsBombObservation, StatsBombOpenDataProvider

__all__ = [
    "APIFootballProvider",
    "DixonColesModel",
    "EloModel",
    "FeedConfigurationError",
    "FeedError",
    "FeedObservation",
    "FeedResponseError",
    "FootballEnsemble",
    "FootballFeedProvider",
    "FootballFeedService",
    "FootballPrediction",
    "MatchFeed",
    "MatchFeatureSnapshot",
    "MatchState",
    "PlayerStatFeed",
    "PoissonModel",
    "ReconciledMatch",
    "SportmonksProvider",
    "StatsBombObservation",
    "StatsBombOpenDataProvider",
    "TeamSnapshot",
    "TeamStatFeed",
]
