from datetime import UTC, datetime

from ois.domains.football_intelligence import (
    CardMarketModel,
    CornerMarketModel,
    FootballMarketModelSuite,
    GoalMarketModel,
    LiveStateModel,
    MatchState,
    PlayerGoalModel,
    ResultMarketModel,
    ShotMarketModel,
    TeamSnapshot,
)


def _match() -> MatchState:
    return MatchState(
        competition="Test League",
        kickoff_at=datetime.now(UTC),
        home=TeamSnapshot(team_id="h", name="Home", attack_strength=1.1, defense_strength=0.95, xg_for=1.5, home_advantage=0.05),
        away=TeamSnapshot(team_id="a", name="Away", attack_strength=0.95, defense_strength=1.05, xg_for=1.2),
    )


def test_goal_model_prices_goal_markets() -> None:
    prediction = GoalMarketModel().predict(_match())
    selections = {(p.market, p.selection) for p in prediction.probabilities}
    assert ("goals_ou", "over_2.5") in selections
    assert ("btts", "yes") in selections
    assert all(0.0 <= p.probability <= 1.0 for p in prediction.probabilities)


def test_result_model_prices_1x2_and_protection_markets() -> None:
    prediction = ResultMarketModel().predict(_match())
    selections = {(p.market, p.selection) for p in prediction.probabilities}
    assert {("1x2", "home"), ("1x2", "draw"), ("1x2", "away")} <= selections
    assert {("double_chance", "1x"), ("double_chance", "12"), ("double_chance", "x2")} <= selections
    assert {("dnb", "home"), ("dnb", "away")} <= selections


def test_non_goal_models_have_distinct_contracts() -> None:
    assert CornerMarketModel().predict().market_family == "corners"
    assert CardMarketModel().predict().market_family == "cards"
    assert ShotMarketModel().predict().market_family == "shots"
    assert PlayerGoalModel().anytime_scorer(0.4).probability > 0.0


def test_live_model_uses_match_clock_and_current_score() -> None:
    early = LiveStateModel().predict(1.4, 1.1, minute=10, current_total_goals=0)
    late = LiveStateModel().predict(1.4, 1.1, minute=80, current_total_goals=0)
    early_rate = early.feature_snapshot["remaining_goal_rate"]
    late_rate = late.feature_snapshot["remaining_goal_rate"]
    assert early_rate > late_rate


def test_suite_exposes_separate_market_models() -> None:
    suite = FootballMarketModelSuite()
    assert suite.goals.model_id != suite.result.model_id
    assert suite.corners.model_id != suite.cards.model_id
    assert suite.shots.model_id != suite.player_goals.model_id
    assert suite.live.model_id != suite.goals.model_id
