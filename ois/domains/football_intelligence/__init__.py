"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration and governed F0-F12 lifecycle primitives.
"""
from .agent import FootballAgent, build_dashboard_payload
from .ensemble import FootballEnsemble
from .lifecycle import FootballIntelligenceOrigin, FootballRunResult, evolution_candidate
from .models import DixonColesModel, EloModel, PoissonModel
from .origin import (
    BacktestEngine, FixtureRecord, FootballSupervisor, OddsSnapshot, ProbabilityCalibrator,
    TeamStrengthModel, WalkForwardEvaluator, XGModel, evidence_event, market_edge, no_vig_probabilities,
)
from .providers import SportmonksProvider
from .schemas import FootballPrediction, MatchState, TeamSnapshot
from .storage import FootballStore

__all__ = [
    "BacktestEngine", "DixonColesModel", "EloModel", "FixtureRecord", "FootballAgent",
    "FootballEnsemble", "FootballIntelligenceOrigin", "FootballPrediction", "FootballRunResult",
    "FootballStore", "FootballSupervisor", "MatchState", "OddsSnapshot", "PoissonModel",
    "ProbabilityCalibrator", "SportmonksProvider", "TeamSnapshot", "TeamStrengthModel",
    "WalkForwardEvaluator", "XGModel", "build_dashboard_payload", "evidence_event", "evolution_candidate",
    "market_edge", "no_vig_probabilities",
]
