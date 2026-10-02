"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration, abstention and governed replay primitives.
"""

from .benchmark import FootballBenchmarkResult, FootballReplayBenchmark
Kernel-agnostic football state, deterministic baselines, market-specific
intelligence, evaluation, evidence and governed agent contracts.
"""

from .agent import FootballAgent, build_dashboard_payload
from .ensemble import FootballEnsemble
from .lifecycle import FootballIntelligenceOrigin, FootballRunResult, evolution_candidate
from .market_models import (
    CardMarketModel,
    CornerMarketModel,
    FootballMarketModelSuite,
    GoalMarketModel,
    LiveStateModel,
    PlayerGoalModel,
    ResultMarketModel,
    ShotMarketModel,
)
from .models import DixonColesModel, EloModel, PoissonModel
from .providers import StatsBombOpenDataProvider, StatsBombReplayInput
from .replay import FootballReplay, FootballReplayResult
from .origin import (
    FixtureRecord,
    FootballSupervisor,
    OddsSnapshot,
    ProbabilityCalibrator,
    TeamStrengthModel,
    XGModel,
    evidence_event,
    market_edge,
    no_vig_probabilities,
)
from .providers import SportmonksProvider
from .safe import EvaluationReport, ValidatedBacktestEngine, WalkForwardEngine, evaluate
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .statsbomb import StatsBombObservation, StatsBombOpenDataProvider
from .storage import FootballStore

__all__ = [
    "CardMarketModel",
    "CornerMarketModel",
    "FootballMarketModelSuite",
    "GoalMarketModel",
    "LiveStateModel",
    "PlayerGoalModel",
    "ResultMarketModel",
    "ShotMarketModel",
    "DixonColesModel",
    "EloModel",
    "FootballBenchmarkResult",
    "EvaluationReport",
    "FixtureRecord",
    "FootballAgent",
    "FootballEnsemble",
    "FootballIntelligenceOrigin",
    "FootballPrediction",
    "FootballReplay",
    "FootballReplayBenchmark",
    "FootballReplayResult",
    "FootballRunResult",
    "FootballStore",
    "FootballSupervisor",
    "MatchState",
    "OddsSnapshot",
    "PoissonModel",
    "StatsBombOpenDataProvider",
    "StatsBombReplayInput",
    "ProbabilityCalibrator",
    "SportmonksProvider",
    "StatsBombObservation",
    "StatsBombOpenDataProvider",
    "TeamSnapshot",
    "TeamStrengthModel",
    "ValidatedBacktestEngine",
    "WalkForwardEngine",
    "XGModel",
    "build_dashboard_payload",
    "evidence_event",
    "evolution_candidate",
    "evaluate",
    "market_edge",
    "no_vig_probabilities",
]
