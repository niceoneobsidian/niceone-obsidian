"""Deterministic value-signal generation from model probabilities and odds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .pricing import MarketPrice, best_prices, devig, edge, expected_value, kelly_fraction


@dataclass(frozen=True, slots=True)
class MarketSignal:
    match_id: str
    market_key: str
    selection: str
    bookmaker: str
    odds: float
    model_probability: float
    fair_probability: float
    probability_edge: float
    expected_value: float
    kelly_fraction: float
    confidence: float
    observed_at: datetime | None
    prediction_timestamp: datetime

    @property
    def positive_value(self) -> bool:
        return self.expected_value > 0 and self.probability_edge > 0


def generate_value_signals(
    *,
    match_id: str,
    market_key: str,
    model_probabilities: dict[str, float],
    prices: list[MarketPrice],
    confidence: float,
    prediction_timestamp: datetime,
    min_edge: float = 0.0,
    min_expected_value: float = 0.0,
    kelly_cap: float = 1.0,
) -> list[MarketSignal]:
    """Generate candidates using only prices observed at or before prediction time."""
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if min_edge < 0 or min_expected_value < 0:
        raise ValueError("minimum thresholds cannot be negative")
    if not 0 < kelly_cap <= 1:
        raise ValueError("kelly_cap must be in (0, 1]")

    fair = devig(prices)
    best = best_prices(prices)
    signals: list[MarketSignal] = []
    for selection, model_probability in model_probabilities.items():
        price = best.get(selection)
        fair_probability = fair.probabilities.get(selection)
        if price is None or fair_probability is None:
            continue
        if price.observed_at is not None and price.observed_at > prediction_timestamp:
            continue
        probability_edge = edge(model_probability, fair_probability)
        ev = expected_value(model_probability, price.odds)
        if probability_edge < min_edge or ev < min_expected_value:
            continue
        signals.append(
            MarketSignal(
                match_id=match_id,
                market_key=market_key,
                selection=selection,
                bookmaker=price.bookmaker,
                odds=price.odds,
                model_probability=model_probability,
                fair_probability=fair_probability,
                probability_edge=probability_edge,
                expected_value=ev,
                kelly_fraction=min(kelly_fraction(model_probability, price.odds), kelly_cap),
                confidence=confidence,
                observed_at=price.observed_at,
                prediction_timestamp=prediction_timestamp,
            )
        )
    return sorted(signals, key=lambda signal: signal.expected_value, reverse=True)
