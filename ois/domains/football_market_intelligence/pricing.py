"""Market pricing primitives: de-vigging, edge, best price, and CLV."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MarketPrice:
    selection: str
    odds: float
    bookmaker: str
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FairMarket:
    probabilities: dict[str, float]
    overround: float


def validate_odds(odds: float) -> None:
    if not isfinite(odds) or odds <= 1.0:
        raise ValueError("decimal odds must be finite and greater than 1")


def implied_probability(odds: float) -> float:
    validate_odds(odds)
    return 1.0 / odds


def devig(prices: list[MarketPrice]) -> FairMarket:
    """Normalize a mutually-exclusive market to a no-vig probability vector."""
    if not prices:
        raise ValueError("at least one market price is required")
    implied = {price.selection: implied_probability(price.odds) for price in prices}
    total = sum(implied.values())
    if total <= 0:
        raise ValueError("market implied probability total must be positive")
    return FairMarket({key: value / total for key, value in implied.items()}, total - 1.0)


def best_prices(prices: list[MarketPrice]) -> dict[str, MarketPrice]:
    result: dict[str, MarketPrice] = {}
    for price in prices:
        validate_odds(price.odds)
        current = result.get(price.selection)
        if current is None or price.odds > current.odds:
            result[price.selection] = price
    return result


def expected_value(model_probability: float, odds: float) -> float:
    if not 0 <= model_probability <= 1:
        raise ValueError("model_probability must be between 0 and 1")
    validate_odds(odds)
    return model_probability * odds - 1.0


def edge(model_probability: float, fair_probability: float) -> float:
    if not 0 <= model_probability <= 1 or not 0 <= fair_probability <= 1:
        raise ValueError("probabilities must be between 0 and 1")
    return model_probability - fair_probability


def kelly_fraction(model_probability: float, odds: float) -> float:
    validate_odds(odds)
    if not 0 <= model_probability <= 1:
        raise ValueError("model_probability must be between 0 and 1")
    b = odds - 1.0
    return max(0.0, (b * model_probability - (1.0 - model_probability)) / b)


def closing_line_value(*, model_probability: float, closing_odds: float) -> float:
    return expected_value(model_probability, closing_odds)
