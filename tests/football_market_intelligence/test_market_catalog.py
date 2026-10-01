from ois.domains.football_market_intelligence.market_catalog import (
    MarketFamily,
    catalog,
    normalize_market_key,
    provider_market_mapping,
)


def test_catalog_covers_major_football_market_families() -> None:
    families = {item.family for item in catalog()}
    assert MarketFamily.RESULT in families
    assert MarketFamily.ASIAN_HANDICAP in families
    assert MarketFamily.CORNERS in families
    assert MarketFamily.CARDS in families
    assert MarketFamily.GOALSCORER in families
    assert MarketFamily.PLAYER_SHOTS_ON_TARGET in families
    assert MarketFamily.OUTRIGHT in families


def test_sportybet_market_ids_are_normalized() -> None:
    assert normalize_market_key("sportybet", "1") == "1x2"
    assert normalize_market_key("sportybet", "16") == "asian_handicap"
    assert normalize_market_key("sportybet", "29") == "btts"
    assert normalize_market_key("sportybet", "45") == "correct_score"
    assert normalize_market_key("sportybet", "47") == "halftime_fulltime"


def test_odds_api_markets_are_normalized() -> None:
    assert normalize_market_key("the-odds-api", "btts") == "btts"
    assert normalize_market_key("the-odds-api", "alternate_totals_corners") == "corners"
    assert normalize_market_key("the-odds-api", "player_shots") == "player_shots"


def test_unknown_provider_market_is_not_fabricated() -> None:
    assert normalize_market_key("unknown-provider", "vendor_999", "vendor-specific market") is None


def test_provider_mapping_is_copy() -> None:
    mapping = provider_market_mapping("sportybet")
    mapping["new"] = "fake"
    assert "new" not in provider_market_mapping("sportybet")
