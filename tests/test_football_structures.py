from datetime import UTC, datetime

from ois.domains.football import (
    DictFixtureRepository,
    FootballGame,
    FootballStatistic,
    FootballTeam,
    Schedule,
    summarize_statistics,
)


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
        kickoff=datetime(2026, 9, 1, tzinfo=UTC),
        home_team_id="a",
        away_team_id="b",
        status="finished",
        home_score=2,
        away_score=1,
    )
    second = FootballGame(
        id="g2",
        kickoff=datetime(2026, 10, 1, tzinfo=UTC),
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
