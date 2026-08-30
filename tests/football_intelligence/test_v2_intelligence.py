from datetime import UTC, datetime

import pytest

from ois.domains.football_intelligence.calibration import evaluate, multiclass_brier
from ois.domains.football_intelligence.ensemble import FootballEnsemble
from ois.domains.football_intelligence.features import build_feature_vector, feature_completeness
from ois.domains.football_intelligence.schemas import FootballEvidence, MatchState, TeamSnapshot
from ois.domains.football_intelligence.simulation import simulate_match


def _match() -> MatchState:
    return MatchState(
        competition="EPL",
        kickoff_at=datetime(2026, 8, 30, 15, tzinfo=UTC),
        home=TeamSnapshot(
            team_id="h", name="Home", elo=1650, attack_strength=1.3, defense_strength=0.9,
            home_advantage=0.08, recent_form=0.2, xg_for=1.7, xg_against=1.0,
            lineup_confidence=0.95, shots_on_target_for=5, shots_on_target_against=3,
            possession=56,
        ),
        away=TeamSnapshot(
            team_id="a", name="Away", elo=1450, attack_strength=0.9, defense_strength=1.2,
            recent_form=-0.1, xg_for=1.1, xg_against=1.4, lineup_confidence=0.9,
            shots_on_target_for=3, shots_on_target_against=5, possession=44,
        ),
        market_home=1.8, market_draw=3.6, market_away=4.8,
        prior_market_home=2.0,
        evidence=[FootballEvidence(source_id="fixture-feed", confidence=0.9, source_type="licensed_feed")],
    )


def test_feature_vector_is_numeric_and_pre_match_only():
    vector = build_feature_vector(_match())
    assert "elo_gap" in vector
    assert all(isinstance(value, float) for value in vector.values())
    assert feature_completeness(_match()) > 0.5


def test_monte_carlo_is_reproducible_and_normalized():
    first = simulate_match(1.7, 1.1, iterations=2_000, correlation=0.08, seed=42)
    second = simulate_match(1.7, 1.1, iterations=2_000, correlation=0.08, seed=42)
    assert first == second
    assert abs(first.home_win + first.draw + first.away_win - 1.0) < 1e-12
    assert first.iterations == 2_000


def test_ensemble_uses_market_and_simulation_without_breaking_contract():
    result = FootballEnsemble().predict(_match(), simulation_seed=7)
    assert result.simulation is not None
    assert result.simulation.iterations == 10_000
    assert abs(result.home_win + result.draw + result.away_win - 1.0) < 1e-9
    assert result.model_ensemble_version == "football-ensemble-v2"


def test_calibration_metrics_require_normalized_probabilities():
    probabilities = [[0.7, 0.2, 0.1], [0.1, 0.2, 0.7], [0.2, 0.6, 0.2]]
    outcomes = [0, 2, 1]
    metrics = evaluate(probabilities, outcomes)
    assert metrics.sample_count == 3
    assert 0 <= metrics.brier_score <= 2
    assert metrics.log_loss > 0
    assert metrics.accuracy == 1.0

    with pytest.raises(ValueError):
        multiclass_brier([[0.8, 0.8, 0.1]], [0])
