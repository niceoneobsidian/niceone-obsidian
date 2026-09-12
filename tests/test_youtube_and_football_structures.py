from datetime import datetime, timezone

from ois.domains.football import (
    DictFixtureRepository,
    FootballGame,
    FootballStatistic,
    FootballTeam,
    Schedule,
    summarize_statistics,
)
from ois.integration.youtube import YouTubeClient, YouTubeOAuthConfig


def test_youtube_oauth_authorization_url_contains_requested_scope() -> None:
    config = YouTubeOAuthConfig(
        client_id="client",
        client_secret="secret",
        redirect_uri="https://example.test/callback",
    )
    url = config.authorization_url("state-123")
    assert "state=state-123" in url
    assert "youtube.readonly" in url
    assert "access_type=offline" in url


def test_youtube_search_normalizes_pagination(monkeypatch) -> None:
    client = YouTubeClient(api_key="test-key")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *args, **kwargs: {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "v1"},
                    "snippet": {"title": "Example", "description": "Demo", "publishedAt": "2026-09-01T00:00:00Z"},
                }
            ],
            "nextPageToken": "next-2",
            "pageInfo": {"totalResults": 1, "resultsPerPage": 1},
        },
    )
    page = client.search_videos("OIS", page_token="next-1")
    assert page.items[0].video_id == "v1"
    assert page.next_page_token == "next-2"


def test_football_team_properties() -> None:
    team = FootballTeam(
        id="t1",
        name="Example FC",
        wins=10,
        draws=4,
        losses=2,
        goals_scored=31,
        goals_against=12,
    )
    assert team.goal_difference == 19
    assert team.record == "10-4-2"


def test_schedule_filters_games_by_team_and_time() -> None:
    first = FootballGame(
        id="g1",
        kickoff=datetime(2026, 9, 1, tzinfo=timezone.utc),
        home_team_id="a",
        away_team_id="b",
        status="finished",
        home_score=2,
        away_score=1,
    )
    second = FootballGame(
        id="g2",
        kickoff=datetime(2026, 10, 1, tzinfo=timezone.utc),
        home_team_id="c",
        away_team_id="a",
        status="scheduled",
    )
    schedule = Schedule([first, second])
    assert [game.id for game in schedule.for_team("a")] == ["g1", "g2"]
    assert [game.id for game in schedule.between(first.kickoff, first.kickoff)] == ["g1"]


def test_local_fixture_repository_and_statistics_summary() -> None:
    repository = DictFixtureRepository({"game": {"fixture_id": "g1"}})
    assert repository.load("game")["fixture_id"] == "g1"

    stats = [
        FootballStatistic(entity_id="t1", metric="shots", value=10),
        FootballStatistic(entity_id="t1", metric="shots", value=14),
    ]
    summary = summarize_statistics(stats)
    assert summary["shots"]["mean"] == 12
