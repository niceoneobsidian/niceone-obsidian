"""OIS Football Intelligence domain."""
from .agent import FootballAgent, build_dashboard_payload
from .ensemble import FootballEnsemble
from .lifecycle import FootballIntelligenceOrigin, FootballRunResult, evolution_candidate
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
]
