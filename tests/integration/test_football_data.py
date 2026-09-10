from datetime import date, datetime, timezone

from ois.integration.football.features import build_player_features
from ois.integration.football.gateway import FootballDataGateway
from ois.integration.football.models import FootballFixture, PlayerSeasonStat


class FakeProvider:
    provider = "fake"

    def fixtures_by_date(self, day: date) -> list[FootballFixture]:
        return [
            FootballFixture(
                provider=self.provider,
                provider_fixture_id="1",
                starting_at=datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc),
                home_team_id="10",
                home_team_name="Arsenal",
                away_team_id="20",
                away_team_name="Napoli",
            )
        ]

    def fixture(self, fixture_id: str) -> FootballFixture:
        return self.fixtures_by_date(date.today())[0]

    def player_match_stats(self, fixture_id: str) -> list[object]:
        return []

    def player_season_stats(self, player_id: str, season_id: str | int) -> list[PlayerSeasonStat]:
        return []


def test_gateway_deduplicates_fixtures_across_providers() -> None:
    gateway = FootballDataGateway([FakeProvider(), FakeProvider()])
    fixtures = gateway.fixtures_by_date(date(2026, 9, 10))
    assert len(fixtures) == 1
    assert fixtures[0].home_team_name == "Arsenal"


def test_player_features_are_rate_normalized() -> None:
    stats = [
        PlayerSeasonStat(
            provider="fake",
            player_id="7",
            season_id="2026",
            minutes=900,
            appearances=10,
            goals=5,
            assists=2,
            shots=20,
            shots_on_target=10,
            passes=450,
            tackles=15,
            interceptions=10,
            cards=2,
            rating=7.4,
        )
    ]
    features = build_player_features(stats)
    assert len(features) == 1
    assert features[0].goals_per_90 == 0.5
    assert features[0].shots_per_90 == 2.0
    assert features[0].rating == 7.4
