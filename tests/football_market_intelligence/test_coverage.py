from datetime import UTC, datetime

from ois.domains.football_market_intelligence.coverage import build_market_coverage
from ois.domains.football_market_intelligence.web_sources import OddsObservation


def odds(bookmaker: str, market: str, match: str, observed_at: datetime) -> OddsObservation:
    return OddsObservation(
        observation_id=f"{bookmaker}-{market}-{match}",
        source_id="the-odds-api",
        external_id=f"ext-{match}-{market}",
        observed_at=observed_at,
        source_timestamp=observed_at,
        source_uri="https://example.test/odds",
        payload_hash="a" * 64,
        provider="The Odds API",
        match_id=match,
        bookmaker=bookmaker,
        provider_market_key=market,
        market_description=market,
        canonical_market_key=market,
        selection="Home",
        decimal_odds=2.0,
        implied_probability=0.5,
    )


def test_build_market_coverage() -> None:
    t1 = datetime(2026, 9, 10, 10, tzinfo=UTC)
    t2 = datetime(2026, 9, 10, 11, tzinfo=UTC)
    coverage = build_market_coverage([
        odds("Book A", "1x2", "m1", t1),
        odds("Book A", "corners", "m1", t2),
        odds("Book A", "corners", "m2", t2),
    ])
    assert len(coverage) == 1
    assert coverage[0].market_keys == ("1x2", "corners")
    assert coverage[0].match_count == 2
    assert coverage[0].observation_count == 3
