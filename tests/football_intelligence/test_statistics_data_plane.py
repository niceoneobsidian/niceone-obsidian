from datetime import UTC, datetime, timedelta

from ois.domains.football_intelligence.statistics_features import player_market_features, team_features
from ois.domains.football_intelligence.statistics_sources import (
    parse_api_football_players,
    parse_api_football_statistics,
)


def test_api_football_team_statistics_are_normalized() -> None:
    raw = {
        "parameters": {"fixture": "101"},
        "response": [
            {
                "team": {"id": 1},
                "statistics": [
                    {"type": "Total Shots", "value": 14},
                    {"type": "Shots on Goal", "value": 6},
                    {"type": "Ball Possession", "value": "58%"},
                    {"type": "Corner Kicks", "value": 7},
                ],
            }
        ],
    }
    result = parse_api_football_statistics(raw)
    assert result[0].shots_total == 14
    assert result[0].shots_on_target == 6
    assert result[0].possession_pct == 58
    assert result[0].corners == 7
    assert result[0].payload_hash


def test_api_football_player_statistics_are_normalized() -> None:
    raw = {
        "parameters": {"fixture": "101"},
        "response": [
            {
                "team": {"id": 1},
                "players": [
                    {
                        "player": {"id": 10, "name": "Player One"},
                        "statistics": [
                            {
                                "games": {"minutes": 90, "rating": "7.8", "position": "F"},
                                "shots": {"total": 4, "on": 2},
                                "goals": {"total": 1, "assists": 1},
                                "passes": {"key": 3, "total": 25},
                                "tackles": {"total": 1, "interceptions": 2},
                                "duels": {"won": 5},
                                "dribbles": {"success": 2},
                                "cards": {"yellow": 1, "red": 0},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = parse_api_football_players(raw)
    assert result[0].player_id == "10"
    assert result[0].goals == 1
    assert result[0].assists == 1
    assert result[0].rating == 7.8
    assert result[0].key_passes == 3


def test_feature_vectors_respect_prediction_time() -> None:
    now = datetime.now(UTC)
    older = {
        "match_id": "1",
        "team_id": "1",
        "shots_total": 10,
        "shots_on_target": 4,
        "corners": 5,
        "possession_pct": 55,
        "source_id": "test",
        "payload_hash": "a",
        "observed_at": now - timedelta(days=1),
    }
    newer = {**older, "match_id": "2", "shots_total": 30, "observed_at": now + timedelta(days=1)}
    vector = team_features([older, newer], as_of=now)
    assert vector.matches == 1
    assert vector.shots_for_avg == 10


def test_player_market_features_filter_player_and_future_data() -> None:
    now = datetime.now(UTC)
    base = {
        "match_id": "1",
        "player_id": "10",
        "player_name": "Player One",
        "team_id": "1",
        "minutes": 90,
        "rating": 8,
        "shots": 5,
        "shots_on_target": 3,
        "goals": 1,
        "assists": 1,
        "key_passes": 2,
        "tackles": 1,
        "yellow_cards": 0,
        "red_cards": 0,
        "source_id": "test",
        "payload_hash": "a",
    }
    from ois.domains.football_intelligence.statistics_sources import PlayerMatchStatistics

    observations = [
        PlayerMatchStatistics(**base, observed_at=now - timedelta(days=1)),
        PlayerMatchStatistics(**base, match_id="2", shots=20, observed_at=now + timedelta(days=1)),
        PlayerMatchStatistics(**base, player_id="11", player_name="Other", observed_at=now - timedelta(days=1)),
    ]
    vector = player_market_features(observations, "10", as_of=now)
    assert vector.matches == 1
    assert vector.shots_avg == 5
