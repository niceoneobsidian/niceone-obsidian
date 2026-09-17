from datetime import UTC, datetime, timedelta

import pytest

from ois.domains.football_market_intelligence.models import MatchFeatures
from ois.domains.football_market_intelligence.pipeline import (
    BookmakerPrice,
    CanonicalEntity,
    EntityResolver,
    FeatureSnapshot,
    HistoricalFeatureStore,
    MarketFeatureBuilder,
    MarketFeatureRequest,
    backtest_probability_series,
    best_available_price,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_entity_resolution_is_provider_agnostic() -> None:
    resolver = EntityResolver()
    entity = CanonicalEntity("team", "team-1", ("Arsenal", "Arsenal FC"), {"api-football": "42"})
    resolver.register(entity)
    assert resolver.resolve("team", "arsenal fc") == entity


def test_feature_store_blocks_future_data() -> None:
    store = HistoricalFeatureStore()
    store.append(FeatureSnapshot("match-1", NOW - timedelta(days=1), MatchFeatures(0, 0, 0, 0)))
    store.append(FeatureSnapshot("match-1", NOW + timedelta(days=1), MatchFeatures(2, 2, 2, 2)))
    builder = MarketFeatureBuilder(store)
    result = builder.build(MarketFeatureRequest("match-1", NOW))
    assert result.features.home_attack == 0


def test_feature_builder_rejects_missing_history() -> None:
    store = HistoricalFeatureStore()
    with pytest.raises(LookupError):
        MarketFeatureBuilder(store).build(MarketFeatureRequest("missing", NOW))


def test_best_price_is_line_shopping_not_model_inference() -> None:
    prices = [
        BookmakerPrice("book-a", "over", 1.60, NOW),
        BookmakerPrice("book-b", "over", 1.75, NOW),
    ]
    assert best_available_price(prices, "over").bookmaker == "book-b"


def test_backtest_is_out_of_sample() -> None:
    report = backtest_probability_series([(0.5, 0)] * 20 + [(0.7, 1)], min_train_size=20)
    assert report.observations == 1
    assert report.mean_brier >= 0
    assert report.mean_log_loss >= 0
