"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, simulation, ensemble
prediction and calibration primitives. Platform registration remains owned by OIS.
"""

from .calibration import CalibrationMetrics, evaluate, multiclass_brier, multiclass_log_loss
from .ensemble import FootballEnsemble
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, SimulationResult, TeamSnapshot
from .simulation import simulate_match

__all__ = [
    "CalibrationMetrics",
    "DixonColesModel",
    "EloModel",
    "FootballEnsemble",
    "FootballPrediction",
    "MatchState",
    "PoissonModel",
    "SimulationResult",
    "TeamSnapshot",
    "evaluate",
    "multiclass_brier",
    "multiclass_log_loss",
    "simulate_match",
]
