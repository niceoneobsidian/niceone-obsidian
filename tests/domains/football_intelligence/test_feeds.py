from __future__ import annotations

from typing import Any

import pytest

from ois.domains.football_intelligence.feeds import (
    APIFootballProvider,
    FeedConfigurationError,
    HttpResponse,
    SportmonksProvider,
)


class FakeTransport:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(
        self, url: str, headers: dict[str, str], params: dict[str, str]
    ) -> HttpResponse:
        self.calls.append((url, params))
        return HttpResponse(status=200, payload=self.payloads[url])


def test_api_football_live_matches_are_normalized() -> None:
    transport = FakeTransport(
        {
            "https://v3.football.api-sports.io/fixtures": {
                "response": [
                    {
                        "fixture": {
                            "id": 10,
                            "date": "2026-09-10T18:00:00+00:00",
                            "status": {"short": "2H", "elapsed": 67},
                        },
                        "league": {"name": "UEFA Champions League"},
                        "teams": {
                            "home": {"id": 1, "name": "Arsenal"},
                            "away": {"id": 2, "name": "Napoli"},
                        },
                        "goals": {"home": 1, "away": 0},
                    }
                ]
            }
        }
    )
    provider = APIFootballProvider(api_key="secret", transport=transport)
    matches = provider.live_matches()

    assert len(matches) == 1
    assert matches[0].provider_match_id == "10"
    assert matches[0].home_team == "Arsenal"
    assert matches[0].minute == 67
    assert matches[0].home_score == 1
    assert matches[0].evidence[0].source_id.startswith("api-football:")
    assert transport.calls[0][1] == {"live": "all"}


def test_api_football_team_and_player_statistics_are_normalized() -> None:
    transport = FakeTransport(
        {
            "https://v3.football.api-sports.io/fixtures/statistics": {
                "response": [
                    {
                        "team": {"id": 1, "name": "Arsenal"},
                        "statistics": [
                            {"type": "Ball Possession", "value": "61%"},
                            {"type": "Total Shots", "value": 12},
                        ],
                    }
                ]
            },
            "https://v3.football.api-sports.io/fixtures/players": {
                "response": [
                    {
                        "team": {"id": 1, "name": "Arsenal"},
                        "players": [
                            {
                                "player": {"id": 99, "name": "Example Player"},
                                "statistics": [
                                    {
                                        "games": {
                                            "minutes": 81,
                                            "position": "F",
                                            "rating": "7.4",
                                        },
                                        "goals": {"total": 1, "assists": 0},
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        }
    )
    provider = APIFootballProvider(api_key="secret", transport=transport)

    teams = provider.match_statistics("10")
    players = provider.player_statistics("10")

    assert teams[0].statistics["Total Shots"] == 12
    assert players[0].minutes == 81
    assert players[0].rating == 7.4
    assert players[0].statistics["goals.total"] == 1


def test_sportmonks_fixture_includes_are_used_for_statistics() -> None:
    transport = FakeTransport(
        {
            "https://api.sportmonks.com/v3/football/fixtures/10": {
                "data": {
                    "participants": [
                        {"id": 1, "name": "Arsenal", "meta": {"location": "home"}},
                        {"id": 2, "name": "Napoli", "meta": {"location": "away"}},
                    ],
                    "statistics": [
                        {"participant_id": 1, "type_id": 34, "data": {"value": 61}},
                    ],
                    "lineups": [
                        {
                            "team_id": 1,
                            "player_id": 99,
                            "player": {"id": 99, "name": "Example Player"},
                            "minutes": 81,
                            "position": "F",
                            "rating": "7.4",
                            "details": [{"type_id": 52, "data": {"value": 3}}],
                        }
                    ],
                }
            }
        }
    )
    provider = SportmonksProvider(token="secret", transport=transport)

    teams = provider.match_statistics("10")
    players = provider.player_statistics("10")

    assert teams[0].team_id == "1"
    assert teams[0].statistics["34"] == {"value": 61}
    assert players[0].player_name == "Example Player"
    assert players[0].statistics["52"] == {"value": 3}
    assert all("include" in params for _, params in transport.calls)


def test_missing_credentials_are_rejected() -> None:
    with pytest.raises(FeedConfigurationError):
        APIFootballProvider(api_key="")
