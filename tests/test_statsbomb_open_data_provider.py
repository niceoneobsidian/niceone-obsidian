from datetime import UTC, datetime

from ois.domains.football_intelligence.providers import StatsBombOpenDataProvider


def _record(match_id: int, date: str, home_id: int, home: str, away_id: int, away: str, hs: int, aws: int) -> dict:
    return {
        "match_id": match_id,
        "match_date": date,
        "kick_off": "15:00:00.000",
        "competition": {"competition_id": 11, "competition_name": "La Liga"},
        "home_team": {"home_team_id": home_id, "home_team_name": home},
        "away_team": {"away_team_id": away_id, "away_team_name": away},
        "home_score": hs,
        "away_score": aws,
    }


def test_statsbomb_provider_uses_only_pre_match_results_for_features() -> None:
    target = _record(3, "2020-09-03", 1, "Home", 2, "Away", 0, 4)
    prior = _record(1, "2020-08-01", 1, "Home", 3, "Other", 2, 0)
    later = _record(2, "2020-10-01", 2, "Away", 1, "Home", 5, 0)
    provider = StatsBombOpenDataProvider(fetch_json=lambda _: [target, prior, later])

    result = provider.load_replay(11, 1, 3)

    assert result.actual_outcome == "away"
    assert result.match.match_id == "3"
    assert result.match.kickoff_at == datetime(2020, 9, 3, 15, 0, tzinfo=UTC)
    assert result.match.home.recent_form == 1.0
    assert result.match.away.recent_form == 0.5
    assert result.source_id == "statsbomb.open-data:11:1:3"
    assert result.raw_match["home_score"] == 0


def test_statsbomb_provider_rejects_unknown_match() -> None:
    provider = StatsBombOpenDataProvider(fetch_json=lambda _: [])

    try:
        provider.load_replay(11, 1, 999)
    except KeyError as exc:
        assert "999" in str(exc)
    else:
        raise AssertionError("unknown match must be rejected")
