from datetime import UTC, datetime

import pytest

from ois.domains.football_intelligence.replay import FootballReplay
from ois.domains.football_intelligence.schemas import MatchState, TeamSnapshot
from ois.runtime.evidence import EvidenceRuntimeV1


def _match() -> MatchState:
    return MatchState(
        match_id="replay-arsenal-demo",
        competition="UCL-replay-fixture",
        kickoff_at=datetime(2026, 9, 1, 19, 0, tzinfo=UTC),
        home=TeamSnapshot(
            team_id="home",
            name="Home FC",
            elo=1600,
            attack_strength=1.15,
            defense_strength=1.05,
            lineup_confidence=0.95,
        ),
        away=TeamSnapshot(
            team_id="away",
            name="Away FC",
            elo=1500,
            attack_strength=0.95,
            defense_strength=1.0,
            lineup_confidence=0.95,
        ),
    )


def test_football_replay_completes_end_to_end() -> None:
    runtime = EvidenceRuntimeV1()
    result = FootballReplay(runtime).run(_match(), actual_outcome="home")
    assert result.outcome_verified is True
    assert result.execution_id.startswith("EXEC-")
    assert result.authorization_id.startswith("AUTH-")
    assert len(result.evidence_ids) == 2
    assert result.evaluation.count == 1
    assert result.evaluation.accuracy in {0.0, 1.0}
    event_types = {event.event_type for event in runtime.ledger.list(result.run_id)}
    assert {
        "EVIDENCE_RECEIVED",
        "ACTION_ADMISSIBILITY_EVALUATED",
        "ACTION_AUTHORIZED",
        "ACTION_EXECUTION_STARTED",
        "ACTION_EXECUTED",
        "OUTCOME_VERIFIED",
        "FOOTBALL_REPLAY_MEASURED",
    }.issubset(event_types)
    assert runtime.ledger.verify() is True


def test_replay_fails_closed_when_evidence_is_stale() -> None:
    runtime = EvidenceRuntimeV1()
    with pytest.raises(PermissionError):
        # Negative freshness is intentionally impossible for a newly ingested fixture.
        FootballReplay(runtime).run(_match(), actual_outcome="home", max_evidence_age_seconds=-1)
