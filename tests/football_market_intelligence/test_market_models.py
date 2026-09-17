from math import isclose

from ois.domains.football_market_intelligence.models import (
    CardModel,
    CornerModel,
    FootballMarketModelSuite,
    GoalModel,
    IsotonicCalibrator,
    LiveStateModel,
    MatchFeatures,
    PlayerGoalModel,
    ResultModel,
    ShotModel,
    MarketFamily,
    abstain_or_publish,
    price_market,
    walk_forward_binary,
)


FEATURES = MatchFeatures(
    home_attack=0.25,
    home_defense=-0.10,
    away_attack=0.05,
    away_defense=-0.05,
    expected_corners=10.5,
    expected_cards=4.2,
    player_goal_rate=0.35,
    player_shot_rate=2.1,
    player_sot_rate=0.9,
)


def test_goal_model_emits_goal_markets() -> None:
    predictions = GoalModel().predict(FEATURES)
    selections = {prediction.selection for prediction in predictions}
    assert {"over", "under", "btts_yes", "btts_no"} <= selections
    assert all(0 <= prediction.probability <= 1 for prediction in predictions)
    assert all(prediction.fair_odds > 1 for prediction in predictions)


def test_result_model_probabilities_sum_to_one() -> None:
    predictions = ResultModel().predict(FEATURES)
    probs = {prediction.selection: prediction.probability for prediction in predictions}
    assert isclose(probs["home"] + probs["draw"] + probs["away"], 1.0, rel_tol=1e-9)


def test_count_models_are_market_specific() -> None:
    corners = CornerModel(10.0).predict(9.5)
    cards = CardModel(4.0).predict(3.5)
    assert all(item.family == MarketFamily.CORNERS for item in corners)
    assert all(item.family == MarketFamily.CARDS for item in cards)


def test_player_models() -> None:
    shots = ShotModel().predict(FEATURES)
    scorer = PlayerGoalModel().predict(FEATURES)
    assert any(item.selection == "shots_over" for item in shots)
    assert scorer.family == MarketFamily.PLAYER_GOALS


def test_live_model_conditions_on_current_score_and_time() -> None:
    live = LiveStateModel().predict(
        MatchFeatures(**{**FEATURES.__dict__, "remaining_minutes": 20, "home_goals": 2, "away_goals": 0})
    )
    assert all(item.family == MarketFamily.LIVE for item in live)


def test_isotonic_calibrator_is_monotone() -> None:
    calibrator = IsotonicCalibrator([0.1, 0.2, 0.3, 0.4], [0, 1, 0, 1])
    values = [calibrator.calibrate(p).calibrated for p in [0.1, 0.2, 0.3, 0.4]]
    assert values == sorted(values)


def test_market_pricing_and_abstention() -> None:
    quote = price_market("home", 0.65, 1.70, min_edge=0.01)
    assert quote.ev > 0
    decision = abstain_or_publish(
        probability=quote.calibrated_probability,
        fair_odds_value=quote.fair_odds,
        market_odds=quote.odds,
        evidence_complete=True,
        calibration_ready=True,
        min_edge=0.01,
    )
    assert decision.publish is True


def test_walk_forward_never_scores_training_rows() -> None:
    observations = [(0.5, 0)] * 20 + [(0.8, 1), (0.7, 0)]
    rows = walk_forward_binary(observations, min_train_size=20)
    assert [row.index for row in rows] == [20, 21]
    assert all(row.brier >= 0 for row in rows)


def test_suite_separates_market_engines() -> None:
    suite = FootballMarketModelSuite.from_features(FEATURES)
    assert suite.goal.model_id != suite.result.model_id
    assert suite.corner.model_id != suite.card.model_id
    assert suite.shot.model_id != suite.player_goal.model_id
