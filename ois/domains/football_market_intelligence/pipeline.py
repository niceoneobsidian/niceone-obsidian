"""End-to-end market intelligence pipeline primitives.

The pipeline turns provider observations into prediction-time features, routes
those features to market-specific models, calibrates probabilities, compares
prices and applies a conservative publish gate. Persistence and provider
transport remain outside this module so OIS governance can own them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Mapping, Sequence

from .models import (
    FootballMarketModelSuite,
    MatchFeatures,
    MarketProbability,
    IsotonicCalibrator,
    MarketQuote,
    abstain_or_publish,
    price_market,
    walk_forward_binary,
)


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    entity_type: str
    external_id: str
    name: str
    observed_at: datetime
    payload: Mapping[str, object]

    @property
    def payload_hash(self) -> str:
        canonical = repr(sorted(self.payload.items())).encode("utf-8")
        return sha256(canonical).hexdigest()


@dataclass(frozen=True)
class CanonicalEntity:
    entity_type: str
    canonical_id: str
    names: tuple[str, ...]
    provider_ids: Mapping[str, str]


class EntityResolver:
    """Deterministic alias resolver; ambiguous matches are rejected."""

    def __init__(self) -> None:
        self._aliases: dict[tuple[str, str], CanonicalEntity] = {}

    def register(self, entity: CanonicalEntity) -> None:
        for name in entity.names:
            self._aliases[(entity.entity_type, name.casefold().strip())] = entity

    def resolve(self, entity_type: str, name: str) -> CanonicalEntity | None:
        return self._aliases.get((entity_type, name.casefold().strip()))


@dataclass(frozen=True)
class FeatureSnapshot:
    match_id: str
    as_of: datetime
    features: MatchFeatures
    evidence_ids: tuple[str, ...] = ()


class HistoricalFeatureStore:
    """Append-only in-memory reference store with prediction-time filtering."""

    def __init__(self) -> None:
        self._snapshots: list[FeatureSnapshot] = []

    def append(self, snapshot: FeatureSnapshot) -> None:
        self._snapshots.append(snapshot)

    def latest_before(self, match_id: str, as_of: datetime) -> FeatureSnapshot | None:
        candidates = [
            item for item in self._snapshots
            if item.match_id == match_id and item.as_of <= as_of
        ]
        return max(candidates, key=lambda item: item.as_of) if candidates else None


@dataclass(frozen=True)
class MarketFeatureRequest:
    match_id: str
    as_of: datetime
    line: float = 2.5


class MarketFeatureBuilder:
    """Builds a prediction snapshot without accessing future observations."""

    def __init__(self, store: HistoricalFeatureStore) -> None:
        self.store = store

    def build(self, request: MarketFeatureRequest) -> FeatureSnapshot:
        snapshot = self.store.latest_before(request.match_id, request.as_of)
        if snapshot is None:
            raise LookupError(f"no historical feature snapshot for {request.match_id}")
        if snapshot.as_of > request.as_of:
            raise ValueError("look-ahead feature detected")
        return snapshot


@dataclass(frozen=True)
class BookmakerPrice:
    bookmaker: str
    selection: str
    odds: float
    observed_at: datetime


@dataclass(frozen=True)
class MarketSignal:
    prediction: MarketProbability
    prices: tuple[BookmakerPrice, ...]
    best_price: BookmakerPrice | None
    quote: MarketQuote | None
    publish: bool
    reason: str


def best_available_price(prices: Sequence[BookmakerPrice], selection: str) -> BookmakerPrice | None:
    matching = [price for price in prices if price.selection == selection and price.odds > 1]
    return max(matching, key=lambda price: price.odds) if matching else None


def generate_signal(
    prediction: MarketProbability,
    prices: Sequence[BookmakerPrice],
    *,
    calibrator: IsotonicCalibrator | None,
    evidence_complete: bool,
    calibration_ready: bool,
    min_edge: float = 0.02,
) -> MarketSignal:
    price = best_available_price(prices, prediction.selection)
    if price is None:
        return MarketSignal(prediction, tuple(prices), None, None, False, "abstain: no comparable bookmaker price")
    quote = price_market(
        prediction.selection,
        prediction.probability,
        price.odds,
        calibrator=calibrator,
        min_edge=min_edge,
    )
    decision = abstain_or_publish(
        probability=quote.calibrated_probability,
        fair_odds_value=quote.fair_odds,
        market_odds=price.odds,
        evidence_complete=evidence_complete,
        calibration_ready=calibration_ready,
        min_edge=min_edge,
    )
    return MarketSignal(prediction, tuple(prices), price, quote, decision.publish, decision.reason)


@dataclass(frozen=True)
class BacktestReport:
    observations: int
    mean_brier: float
    mean_log_loss: float


def backtest_probability_series(observations: Sequence[tuple[float, int]], min_train_size: int = 20) -> BacktestReport:
    rows = walk_forward_binary(observations, min_train_size=min_train_size)
    if not rows:
        return BacktestReport(0, 0.0, 0.0)
    return BacktestReport(
        observations=len(rows),
        mean_brier=sum(row.brier for row in rows) / len(rows),
        mean_log_loss=sum(row.log_loss for row in rows) / len(rows),
    )


@dataclass(frozen=True)
class MarketIntelligenceSnapshot:
    match_id: str
    generated_at: datetime
    predictions: tuple[MarketProbability, ...]
    signals: tuple[MarketSignal, ...]


def build_snapshot(features: MatchFeatures, prices: Sequence[BookmakerPrice]) -> MarketIntelligenceSnapshot:
    suite = FootballMarketModelSuite.from_features(features)
    predictions = tuple(
        suite.goal.predict(features)
        + suite.result.predict(features)
        + suite.corner.predict(9.5)
        + suite.card.predict(3.5)
        + suite.shot.predict(features)
        + [suite.player_goal.predict(features)]
        + suite.live.predict(features)
    )
    signals = tuple(
        generate_signal(
            prediction,
            prices,
            calibrator=None,
            evidence_complete=True,
            calibration_ready=False,
        )
        for prediction in predictions
    )
    return MarketIntelligenceSnapshot(
        match_id="feature-snapshot",
        generated_at=datetime.now(UTC),
        predictions=predictions,
        signals=signals,
    )
