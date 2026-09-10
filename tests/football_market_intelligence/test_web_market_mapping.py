from datetime import UTC, datetime

from ois.domains.football_market_intelligence.web_adapters import parse_odds_api, parse_sportmonks_odds


OBSERVED_AT = datetime(2026, 9, 10, 12, tzinfo=UTC)


def test_odds_api_normalizes_market_keys() -> None:
    payload = {
        "data": [
            {
                "id": "event-1",
                "bookmakers": [
                    {
                        "key": "example",
                        "title": "Example Book",
                        "markets": [
                            {
                                "key": "alternate_totals_corners",
                                "title": "Corners",
                                "last_update": "2026-09-10T11:00:00Z",
                                "outcomes": [{"name": "Over", "point": 8.5, "price": 1.90}],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    records = parse_odds_api(payload, source_uri="https://example.test", observed_at=OBSERVED_AT)
    assert records[0].canonical_market_key == "corners"
    assert records[0].provider_market_key == "alternate_totals_corners"
    assert records[0].line == 8.5


def test_sportmonks_preserves_provider_market_id() -> None:
    payload = {
        "data": [
            {
                "id": 100,
                "fixture_id": 200,
                "bookmaker_id": 3,
                "market_id": 16,
                "market_description": "Asian Handicap",
                "label": "Home",
                "line": -1.5,
                "value": "1.95",
                "last_update": "2026-09-10T11:00:00Z",
            }
        ]
    }
    records = parse_sportmonks_odds(payload, source_uri="https://example.test", observed_at=OBSERVED_AT)
    assert records[0].provider_market_key == "16"
    assert records[0].market_description == "Asian Handicap"
    assert records[0].canonical_market_key == "asian_handicap"
