"""Tests for pricing, value detection, and walk-forward market backtesting."""

from datetime import UTC, datetime, timedelta

import pytest

from ois.domains.football_market_intelligence.backtest import BacktestConfig, run_backtest
from ois.domains.football_market_intelligence.engine import generate_value_signals
from ois.domains.football_market_intelligence.pricing import MarketPrice, devig, expected_value, kelly_fraction

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def test_devig_normalizes_overround() -> None:
    fair = devig([
        MarketPrice("home", 2.0, "a"),
        MarketPrice("draw", 3.5, "a"),
        MarketPrice("away", 4.0, "a"),
    ])
    assert sum(fair.probabilities.values()) == pytest.approx(1.0)
    assert fair.overround > 0


def test_value_engine_uses_best_non_future_price() -> None:
    signals = generate_value_signals(
        match_id="m1",
        market_key="result",
        model_probabilities={"home": 0.60, "draw": 0.20, "away": 0.20},
        prices=[
            MarketPrice("home", 2.0, "book-a", NOW - timedelta(minutes=5)),
            MarketPrice("home", 2.2, "book-b", NOW + timedelta(minutes=1)),
            MarketPrice("draw", 3.5, "book-a", NOW - timedelta(minutes=5)),
            MarketPrice("away", 4.0, "book-a", NOW - timedelta(minutes=5)),
        ],
        confidence=0.9,
        prediction_timestamp=NOW,
        min_edge=0.02,
    )
    assert len(signals) == 1
    assert signals[0].selection == "home"
    assert signals[0].odds == 2.0


def test_expected_value_and_kelly() -> None:
    assert expected_value(0.60, 2.0) == pytest.approx(0.20)
    assert kelly_fraction(0.60, 2.0) == pytest.approx(0.20)


def test_backtest_is_chronological_and_fractional_kelly() -> None:
    signals = generate_value_signals(
        match_id="m1",
        market_key="result",
        model_probabilities={"home": 0.60},
        prices=[MarketPrice("home", 2.0, "book", NOW)],
        confidence=0.9,
        prediction_timestamp=NOW,
    )
    result = run_backtest(
        signals,
        {("m1", "home"): True},
        {"m1": NOW + timedelta(hours=2)},
        BacktestConfig(starting_bankroll=100, kelly_fraction=0.25, max_stake_fraction=0.10),
    )
    assert len(result.bets) == 1
    assert result.ending_bankroll > 100


def test_backtest_skips_missing_outcomes() -> None:
    signals = generate_value_signals(
        match_id="m2",
        market_key="result",
        model_probabilities={"home": 0.60},
        prices=[MarketPrice("home", 2.0, "book", NOW)],
        confidence=0.9,
        prediction_timestamp=NOW,
    )
    result = run_backtest(signals, {}, {"m2": NOW + timedelta(hours=2)})
    assert result.bets == ()
