from datetime import UTC, datetime

from ois.domains.football_intelligence.benchmark import FootballReplayBenchmark
from ois.domains.football_intelligence.schemas import FootballPrediction


def _record(match_id: int, date: str, home_id: int, away_id: int, hs: int, aws: int) -> dict:
    return {
        "match_id": match_id,
        "match_date": date,
        "kick_off": "15:00:00.000",
        "competition": {"competition_id": 11, "competition_name": "La Liga"},
        "home_team": {"home_team_id": home_id, "home_team_name": f"Team {home_id}"},
        "away_team": {"away_team_id": away_id, "away_team_name": f"Team {away_id}"},
        "home_score": hs,
        "away_score": aws,
    }


class _Provider:
    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def load_matches(self, competition_id: int, season_id: int) -> list[dict]:
        return self.records

    @staticmethod
    def _kickoff(record: dict) -> datetime:
        return datetime.fromisoformat(f"{record['match_date']}T{record['kick_off'][:8]}").replace(tzinfo=UTC)

    @staticmethod
    def _outcome(record: dict) -> str:
        if record["home_score"] > record["away_score"]:
            return "home"
        if record["away_score"] > record["home_score"]:
            return "away"
        return "draw"


class _Replay:
    def run_statsbomb(self, competition_id: int, season_id: int, match_id: int, *, provider: _Provider) -> object:
        record = next(item for item in provider.records if item["match_id"] == match_id)
        outcome = provider._outcome(record)
        probabilities = {"home": 0.8, "draw": 0.1, "away": 0.1}
        if outcome == "away":
            probabilities = {"home": 0.1, "draw": 0.1, "away": 0.8}
        prediction = FootballPrediction(
            match_id=str(match_id),
            home_win=probabilities["home"],
            draw=probabilities["draw"],
            away_win=probabilities["away"],
            expected_home_goals=1.0,
            expected_away_goals=1.0,
            confidence=0.8,
            model_agreement=1.0,
            data_completeness=1.0,
        )
        return type("ReplayResult", (), {"prediction": prediction})()


def test_benchmark_is_dataset_pinned_and_measures_corpus() -> None:
    records = [
        _record(1, "2020-08-01", 1, 2, 2, 0),
        _record(2, "2020-08-08", 2, 1, 0, 1),
        _record(3, "2020-08-15", 1, 2, 1, 0),
    ]
    benchmark = FootballReplayBenchmark(provider=_Provider(records), replay=_Replay())

    result = benchmark.run(11, 1, limit=2, min_history_matches=1)

    assert result.requested_matches == 2
    assert result.evaluated_matches == 2
    assert result.failed_matches == 0
    assert result.skipped_matches == 0
    assert result.dataset_digest
    assert result.metrics.count == 2
    assert result.metrics.accuracy == 1.0


def test_benchmark_skips_matches_without_history() -> None:
    records = [_record(1, "2020-08-01", 1, 2, 2, 0)]
    benchmark = FootballReplayBenchmark(provider=_Provider(records), replay=_Replay())

    result = benchmark.run(11, 1, min_history_matches=1)

    assert result.evaluated_matches == 0
    assert result.skipped_matches == 1
    assert result.metrics.count == 0
