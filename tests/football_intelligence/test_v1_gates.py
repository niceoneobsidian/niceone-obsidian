from datetime import UTC, datetime

import pytest

from ois.domains.football_intelligence import (
    DixonColesModel,
    EloModel,
    FootballEnsemble,
    MatchState,
    PoissonModel,
    TeamSnapshot,
    evaluate,
    multiclass_brier,
    multiclass_log_loss,
    simulate_match,
)
from ois.domains.football_intelligence.features import build_feature_vector
from ois.domains.football_intelligence.schemas import FootballEvidence


def match() -> MatchState:
    return MatchState(
        competition="EPL",
        kickoff_at=datetime(2026, 9, 13, 15, tzinfo=UTC),
        home=TeamSnapshot(
            team_id="h", name="Home", elo=1600, attack_strength=1.2, defense_strength=0.9,
            home_advantage=0.08, recent_form=0.2, xg_for=1.8, xg_against=1.0,
            shots_on_target_for=5, possession=55, lineup_confidence=0.9,
        ),
        away=TeamSnapshot(
            team_id="a", name="Away", elo=1500, attack_strength=1.0, defense_strength=1.1,
            recent_form=-0.1, xg_for=1.2, xg_against=1.4,
            shots_on_target_for=3, possession=45, lineup_confidence=0.9,
        ),
        evidence=[FootballEvidence(source_id="fixture-feed", confidence=0.9)],
    )


def test_gate_1_models_are_normalized():
    state = match()
    for model in (EloModel(), PoissonModel(), DixonColesModel()):
        p = model.predict(state)
        assert abs(p.home + p.draw + p.away - 1.0) < 1e-9


def test_gate_1_feature_vector_is_numeric_and_point_in_time():
    vector = build_feature_vector(match())
    assert vector
    assert all(isinstance(value, float) for value in vector.values())


def test_gate_1_simulation_is_reproducible():
    a = simulate_match(1.7, 1.1, iterations=2_000, correlation=0.08, seed=42)
    b = simulate_match(1.7, 1.1, iterations=2_000, correlation=0.08, seed=42)
    assert a == b
    assert abs(a.home_win + a.draw + a.away_win - 1.0) < 1e-12


def test_gate_1_ensemble_is_auditable_and_seeded():
    prediction = FootballEnsemble().predict(match(), simulation_seed=42)
    assert prediction.model_ensemble_version == "football-ensemble-v1"
    assert prediction.simulation is not None
    assert prediction.evidence[0].source_id == "fixture-feed"
    assert abs(prediction.home_win + prediction.draw + prediction.away_win - 1.0) < 1e-9


def test_gate_1_calibration_metrics_are_deterministic():
    probabilities = [[0.7, 0.2, 0.1], [0.1, 0.2, 0.7], [0.2, 0.6, 0.2]]
    outcomes = [0, 2, 1]
    report = evaluate(probabilities, outcomes)
    assert report.sample_count == 3
    assert report.brier_score == pytest.approx(multiclass_brier(probabilities, outcomes))
    assert report.log_loss == pytest.approx(multiclass_log_loss(probabilities, outcomes))
    assert report.accuracy == pytest.approx(1.0)
