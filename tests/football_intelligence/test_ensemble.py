from datetime import UTC, datetime

from ois.domains.football_intelligence.ensemble import FootballEnsemble
from ois.domains.football_intelligence.schemas import MatchState, TeamSnapshot


def test_ensemble_produces_auditable_prediction() -> None:
    match = MatchState(
        competition="EPL",
        kickoff_at=datetime(2026, 8, 30, 15, tzinfo=UTC),
        home=TeamSnapshot(
            team_id="h",
            name="Home",
            elo=1650,
            attack_strength=1.3,
            defense_strength=0.9,
            home_advantage=0.08,
            lineup_confidence=0.9,
        ),
        away=TeamSnapshot(
            team_id="a",
            name="Away",
            elo=1450,
            attack_strength=0.9,
            defense_strength=1.2,
            lineup_confidence=0.9,
        ),
    )
    result = FootballEnsemble().predict(match)
    assert abs(result.home_win + result.draw + result.away_win - 1.0) < 1e-9
    assert 0 <= result.confidence <= 1
    assert 0 <= result.model_agreement <= 1
    assert len(result.models) == 3
    assert result.as_audit_record()["match_id"] == match.match_id
