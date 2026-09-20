from datetime import UTC, datetime

from ois.domains.football_intelligence import DixonColesModel, EloModel, PoissonModel
from ois.domains.football_intelligence.schemas import MatchState, TeamSnapshot


def match() -> MatchState:
    return MatchState(
        competition="EPL",
        kickoff_at=datetime(2026, 8, 30, 15, tzinfo=UTC),
        home=TeamSnapshot(
            team_id="h",
            name="Home",
            elo=1600,
            attack_strength=1.2,
            defense_strength=0.9,
            home_advantage=0.08,
        ),
        away=TeamSnapshot(
            team_id="a", name="Away", elo=1500, attack_strength=1.0, defense_strength=1.1
        ),
    )


def test_baselines_return_normalized_probabilities():
    for model in (EloModel(), PoissonModel(), DixonColesModel()):
        prediction = model.predict(match())
        assert abs(prediction.home + prediction.draw + prediction.away - 1.0) < 1e-9
        assert prediction.expected_home_goals >= 0
        assert prediction.expected_away_goals >= 0


def test_dixon_coles_is_normalized_and_distinct():
    base = PoissonModel().predict(match())
    dc = DixonColesModel().predict(match())
    assert abs(dc.home + dc.draw + dc.away - 1.0) < 1e-9
    assert dc.draw >= base.draw
