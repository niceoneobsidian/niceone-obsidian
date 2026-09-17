from datetime import UTC, datetime

from ois.domains.football_market_intelligence.models import MatchFeatures
from ois.domains.football_market_intelligence.pipeline import FeatureSnapshot, HistoricalFeatureStore
from ois.domains.football_market_intelligence.training import TrainingRow, fit_seven_models, rows_from_snapshots


def _row(i: int, home: int, away: int, corners: int, cards: int) -> TrainingRow:
    return TrainingRow(
        match_id=f"m{i}",
        as_of_rank=i,
        features=MatchFeatures(1.2, 1.1, 1.0, 1.0, expected_corners=8.5, expected_cards=3.5, player_shot_rate=1.4, player_sot_rate=0.5, player_goal_rate=0.2),
        home_goals=home,
        away_goals=away,
        corners=corners,
        cards=cards,
        player_shots=2,
        player_sot=1,
        player_scored=i % 2,
        live_goal=i % 2,
    )


def test_all_seven_models_fit_from_empirical_rows() -> None:
    models = fit_seven_models(tuple(_row(i, i % 3, (i + 1) % 2, 7 + i % 4, 2 + i % 3) for i in range(30)))
    assert models.training_rows == 30
    assert models.goal.home_rate > 0
    assert models.goal.away_rate > 0
    assert abs(sum(models.result.predict(MatchFeatures(1, 1, 1, 1)).values()) - 1) < 1e-9
    assert models.corner.rate > 0
    assert models.card.rate > 0
    assert models.shot.shot_rate > 0
    assert models.player_goal.predict() >= 0
    assert models.live.predict(MatchFeatures(1, 1, 1, 1, remaining_minutes=30))["next_goal_yes"] > 0


def test_feature_store_join_respects_prediction_time() -> None:
    store = HistoricalFeatureStore()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    store.append(FeatureSnapshot("m1", t0, MatchFeatures(1, 1, 1, 1)))
    assert store.latest_before("m1", t0) is not None
    assert store.latest_before("m1", datetime(2025, 12, 31, tzinfo=UTC)) is None


def test_snapshot_outcome_join_is_deterministic() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    snapshots = [FeatureSnapshot(f"m{i}", t0, MatchFeatures(1, 1, 1, 1)) for i in range(2)]
    rows = rows_from_snapshots(snapshots, {"m0": {"home_goals": 1, "away_goals": 0}, "m1": {"home_goals": 0, "away_goals": 0}})
    assert [row.match_id for row in rows] == ["m0", "m1"]
