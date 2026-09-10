from datetime import UTC, datetime, timedelta

import pytest

from ois.domains.football_market_intelligence.web_adapters import (
    FOOTBALL_DATA,
    ODDS_API,
    SPORTMONKS,
    parse_football_data_matches,
    parse_odds_api,
    parse_sportmonks_odds,
)
from ois.domains.football_market_intelligence.web_normalization import (
    assert_temporal_integrity,
    normalize_observations,
)
from ois.domains.football_market_intelligence.web_sources import implied_probability


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def test_football_data_match_is_normalized() -> None:
    payload = {
        "matches": [
            {
                "id": 123,
                "utcDate": "2026-09-10T18:00:00Z",
                "status": "SCHEDULED",
                "competition": {"code": "PL"},
                "homeTeam": {"id": 1, "name": "Arsenal FC"},
                "awayTeam": {"id": 2, "name": "Liverpool FC"},
                "score": {"fullTime": {"home": None, "away": None}},
            }
        ]
    }
    records = parse_football_data_matches(payload, source_uri="/v4/matches", observed_at=NOW)
    assert len(records) == 1
    assert records[0].external_id == "123"
    assert records[0].competition == "PL"
    assert records[0].home_team_name == "Arsenal FC"


def test_odds_api_normalizes_bookmaker_outcome() -> None:
    payload = {
        "data": [
            {
                "id": "event-1",
                "bookmakers": [
                    {
                        "key": "example",
                        "title": "Example Bookmaker",
                        "markets": [
                            {
                                "key": "totals",
                                "outcomes": [{"name": "Over", "price": 1.8, "point": 2.5}],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    records = parse_odds_api(payload, source_uri="/v4/historical/sports/soccer/odds", observed_at=NOW)
    assert len(records) == 1
    assert records[0].match_id == "event-1"
    assert records[0].market_type == "totals"
    assert records[0].line == pytest.approx(2.5)
    assert records[0].implied_probability == pytest.approx(1 / 1.8)


def test_sportmonks_normalizes_probability_and_timestamp() -> None:
    payload = {
        "data": [
            {
                "id": 77,
                "fixture_id": 555,
                "market_id": 1,
                "bookmaker_id": 2,
                "label": "Home",
                "value": "2.10",
                "latest_bookmaker_update": "2026-09-10 11:30:00",
            }
        ]
    }
    records = parse_sportmonks_odds(payload, source_uri="/odds/premium/fixtures/555", observed_at=NOW)
    assert len(records) == 1
    assert records[0].match_id == "555"
    assert records[0].decimal_odds == pytest.approx(2.10)
    assert records[0].source_timestamp is not None


def test_implied_probability_rejects_invalid_odds() -> None:
    with pytest.raises(ValueError, match="greater than 1"):
        implied_probability(1.0)


def test_future_market_evidence_is_rejected_for_prediction() -> None:
    payload = {
        "data": [
            {
                "id": "event-1",
                "bookmakers": [
                    {
                        "key": "example",
                        "markets": [
                            {"key": "h2h", "outcomes": [{"name": "Home", "price": 2.0}]}
                        ],
                    }
                ],
            }
        ]
    }
    observations = parse_odds_api(payload, source_uri="/historical", observed_at=NOW)
    observations[0].source_timestamp = NOW + timedelta(minutes=5)
    normalized = normalize_observations(
        ODDS_API,
        observations,
        prediction_created_at=NOW,
    )
    assert normalized.records == []
    assert normalized.rejected_count == 1
    assert "future observation" in normalized.warnings[0]


def test_temporal_integrity_fails_closed() -> None:
    payload = {
        "data": [
            {
                "id": "event-1",
                "bookmakers": [],
            }
        ]
    }
    observations = parse_odds_api(payload, source_uri="/historical", observed_at=NOW)
    assert_temporal_integrity(observations, NOW)


def test_source_contracts_are_provider_specific() -> None:
    assert FOOTBALL_DATA.historical is True
    assert ODDS_API.kind == "odds"
    assert SPORTMONKS.provider == "Sportmonks"
