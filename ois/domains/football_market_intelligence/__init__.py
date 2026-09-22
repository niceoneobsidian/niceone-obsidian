"""OIS Football Market Intelligence domain.

Deterministic market translation, settlement, evaluation and attribution primitives.
Execution, policy, persistence and promotion remain owned by OIS platform services.
"""

from .evaluation import evaluate_market_event
from .integration import translate_market
from .markets import MarketType, Selection
from .schemas import MarketEvent, MarketOutcome
from .settlement import settle_market

__all__ = [
    "MarketEvent",
    "MarketOutcome",
    "MarketType",
    "Selection",
    "evaluate_market_event",
    "settle_market",
    "translate_market",
]
