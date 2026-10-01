from datetime import UTC, datetime

import pytest

from ois.domains.football_intelligence.schemas import FootballPrediction
from ois.domains.football_market_intelligence.evaluation import (
    aggregate_market_evaluations,
    evaluate_market_event,
)
from ois.domains.football_market_intelligence.markets import MarketType, Selection
from ois.domains.football_market_intelligence.registry import manifest
from ois.domains.football_market_intelligence.schemas import MarketEvent, OutcomeStatus
from ois.domains.football_market_intelligence.settlement import settle_market


def prediction() -> FootballPrediction:
    return FootballPrediction(
        match_id="match-1",
        home_win=0.50,
        draw=0.25,
        away_win=0.25,
        expected_home_goals=1.7,
        expected_away_goals=1.0,
        confidence=0.8,
        model_agreement=0.9,
        data_completeness=0.95,
        created_at=datetime.now(UTC),
    )


def event(
    market_type: MarketType, selection: Selection, *, line: float | None = None
) -> MarketEvent:
    return MarketEvent.from_prediction(
        prediction(),
        market_type=market_type,
        selection=selection,
        odds=2.0,
        model_probability=0.60,
        line=line,
    )


def test_result_settlement() -> None:
    result = settle_market(event(MarketType.RESULT, Selection.HOME_WIN), 2, 1)
    assert result.status is OutcomeStatus.WIN


def test_double_chance_settlement() -> None:
    result = settle_market(event(MarketType.DOUBLE_CHANCE, Selection.HOME_OR_DRAW), 1, 1)
    assert result.status is OutcomeStatus.WIN


def test_total_goals_push() -> None:
    result = settle_market(event(MarketType.TOTAL_GOALS, Selection.OVER, line=2.0), 1, 1)
    assert result.status is OutcomeStatus.PUSH


def test_team_goals_settlement() -> None:
    result = settle_market(event(MarketType.TEAM_GOALS, Selection.AWAY_UNDER, line=1.5), 2, 1)
    assert result.status is OutcomeStatus.WIN


def test_btts_settlement() -> None:
    result = settle_market(event(MarketType.BTTS, Selection.BTTS_YES), 2, 1)
    assert result.status is OutcomeStatus.WIN


def test_handicap_push() -> None:
    result = settle_market(event(MarketType.HANDICAP, Selection.HOME_HANDICAP, line=-1.0), 2, 1)
    assert result.status is OutcomeStatus.PUSH


def test_special_1up_reference_semantics() -> None:
    result = settle_market(event(MarketType.SPECIAL, Selection.HOME_1UP), 2, 1)
    assert result.status is OutcomeStatus.WIN


def test_evaluation_preserves_edge_and_roi() -> None:
    market = event(MarketType.RESULT, Selection.HOME_WIN)
    outcome = settle_market(market, 2, 0)
    evaluation = evaluate_market_event(market, outcome)
    assert evaluation.correct is True
    assert evaluation.edge == pytest.approx(0.10)
    assert evaluation.roi_if_staked == pytest.approx(1.0)


def test_aggregate_metrics() -> None:
    winning_market = event(MarketType.RESULT, Selection.HOME_WIN)
    losing_market = event(MarketType.RESULT, Selection.HOME_WIN)
    evaluations = [
        evaluate_market_event(winning_market, settle_market(winning_market, 2, 0)),
        evaluate_market_event(losing_market, settle_market(losing_market, 0, 2)),
    ]
    metrics = aggregate_market_evaluations(evaluations)
    assert metrics["count"] == 2
    assert metrics["decided_count"] == 2
    assert metrics["accuracy"] == pytest.approx(0.5)


def test_invalid_market_selection_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid"):
        MarketEvent.from_prediction(
            prediction(),
            market_type=MarketType.BTTS,
            selection=Selection.HOME_WIN,
            odds=2.0,
            model_probability=0.5,
        )


def test_manifest_contains_market_capabilities() -> None:
    data = manifest()
    ids = {item["capability_id"] for item in data["capabilities"]}
    assert "football.market_translate" in ids
    assert "football.market_settle" in ids
    assert "football.market_evaluate" in ids
