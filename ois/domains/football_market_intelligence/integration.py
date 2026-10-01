"""Integration boundary for governed OIS football market capabilities."""

from __future__ import annotations

from typing import Any

from ois.domains.football_intelligence.schemas import FootballPrediction

from .evaluation import evaluate_market_event
from .markets import MarketType, Selection
from .registry import manifest
from .schemas import MarketEvaluation, MarketEvent, MarketOutcome
from .settlement import settle_market

DOMAIN_ID = "football_market_intelligence"


def domain_manifest() -> dict[str, Any]:
    """Return declarative registration data; OIS platform registries stay authoritative."""
    return manifest()


def translate_market(
    prediction: FootballPrediction,
    *,
    market_type: MarketType,
    selection: Selection,
    odds: float,
    model_probability: float,
    line: float | None = None,
) -> MarketEvent:
    """Translate an existing football prediction into one atomic market event."""
    return MarketEvent.from_prediction(
        prediction,
        market_type=market_type,
        selection=selection,
        odds=odds,
        model_probability=model_probability,
        line=line,
    )


def settle_and_evaluate(
    event: MarketEvent, home_goals: int, away_goals: int
) -> tuple[MarketOutcome, MarketEvaluation]:
    """Deterministically settle and evaluate a completed match."""
    outcome = settle_market(event, home_goals, away_goals)
    return outcome, evaluate_market_event(event, outcome)
