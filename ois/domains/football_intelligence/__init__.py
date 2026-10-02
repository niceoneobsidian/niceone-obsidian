"""OIS Football Intelligence domain."""
from .agent import FootballAgent, build_dashboard_payload
from .ensemble import FootballEnsemble
from .lifecycle import FootballIntelligenceOrigin, FootballRunResult, evolution_candidate
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
from .origin import FixtureRecord, FootballSupervisor, OddsSnapshot, ProbabilityCalibrator, TeamStrengthModel, XGModel, evidence_event, market_edge, no_vig_probabilities
from .providers import SportmonksProvider
from .safe import EvaluationReport, ValidatedBacktestEngine, WalkForwardEngine, evaluate
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .storage import FootballStore

__all__ = [
    "DixonColesModel", "EloModel", "EvaluationReport", "FixtureRecord", "FootballAgent", "FootballEnsemble",
    "FootballIntelligenceOrigin", "FootballPrediction", "FootballRunResult", "FootballStore", "FootballSupervisor",
    "MatchState", "OddsSnapshot", "PoissonModel", "ProbabilityCalibrator", "SportmonksProvider", "TeamSnapshot",
    "TeamStrengthModel", "ValidatedBacktestEngine", "WalkForwardEngine", "XGModel", "build_dashboard_payload",
    "evidence_event", "evolution_candidate", "evaluate", "market_edge", "no_vig_probabilities",
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
