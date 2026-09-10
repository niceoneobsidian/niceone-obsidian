"""OIS Football Intelligence domain.

Kernel-agnostic football state, deterministic baselines, ensemble prediction,
calibration, abstention and governed replay primitives.
"""

from .ensemble import FootballEnsemble
from .models import DixonColesModel, EloModel, PoissonModel
from .providers import StatsBombOpenDataProvider, StatsBombReplayInput
from .replay import FootballReplay, FootballReplayResult
from .schemas import FootballPrediction, MatchState, TeamSnapshot

__all__ = [
    "DixonColesModel",
    "EloModel",
    "FootballEnsemble",
    "FootballPrediction",
    "FootballReplay",
    "FootballReplayResult",
    "MatchState",
    "PoissonModel",
    "StatsBombOpenDataProvider",
    "StatsBombReplayInput",
    "TeamSnapshot",
]
