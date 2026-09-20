"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration and abstention primitives. Platform registration remains owned by OIS.
"""

from .ensemble import FootballEnsemble
from .models import DixonColesModel, EloModel, PoissonModel
from .schemas import FootballPrediction, MatchState, TeamSnapshot

__all__ = [
    "DixonColesModel",
    "EloModel",
    "FootballEnsemble",
    "FootballPrediction",
    "MatchState",
    "PoissonModel",
    "TeamSnapshot",
]
