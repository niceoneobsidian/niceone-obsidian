from __future__ import annotations

from datetime import UTC, datetime

from ois.domains.football_intelligence.feed_service import FootballFeedService
from ois.domains.football_intelligence.feeds import MatchFeed, PlayerStatFeed, TeamStatFeed


class FakeProvider:
    provider_name = "fake"

    def __init__(self, matches: tuple[MatchFeed, ...]) -> None:
        self.matches = matches

    def live_matches(self) -> tuple[MatchFeed, ...]:
        return self.matches

    def match_statistics(self, match_id: str) -> tuple[TeamStatFeed, ...]:
        return ()

    def player_statistics(self, match_id: str) -> tuple[PlayerStatFeed, ...]:
        return ()


def _match(home: str, away: str, kickoff: str) -> MatchFeed:
    return MatchFeed(
        provider="fake",
        provider_match_id=f"{home}-{away}-{kickoff}",
        competition="League",
        kickoff_at=datetime.fromisoformat(kickoff),
        status="LIVE",
        home_team_id=home,
        home_team=home,
        away_team_id=away,
        away_team=away,
    )


def test_reconciliation_does_not_collapse_same_teams_at_different_kickoffs() -> None:
    provider = FakeProvider(
        (
            _match("Arsenal", "Chelsea", "2026-10-01T15:00:00+00:00"),
            _match("Arsenal", "Chelsea", "2026-10-02T15:00:00+00:00"),
        )
    )

    matches = FootballFeedService((provider,)).live_matches()

    assert len(matches) == 2


def test_reconciliation_deduplicates_same_fixture_across_providers() -> None:
    first = _match("Arsenal", "Chelsea", "2026-10-01T15:00:00+00:00")
    second = first.model_copy(update={"provider": "second-provider", "provider_match_id": "2"})

    class SecondProvider(FakeProvider):
        provider_name = "second-provider"

    service = FootballFeedService((FakeProvider((first,)), SecondProvider((second,))))

    matches = service.live_matches()

    assert len(matches) == 1
    assert matches[0].sources == ("fake", "second-provider")


def test_empty_provider_set_is_rejected() -> None:
    try:
        FootballFeedService(())
    except ValueError as exc:
        assert "At least one football feed provider" in str(exc)
    else:
        raise AssertionError("Expected an empty provider set to be rejected")


def test_kickoff_is_timezone_aware() -> None:
    match = _match("Arsenal", "Chelsea", "2026-10-01T15:00:00+00:00")
    assert match.kickoff_at is not None
    assert match.kickoff_at.tzinfo is UTC
