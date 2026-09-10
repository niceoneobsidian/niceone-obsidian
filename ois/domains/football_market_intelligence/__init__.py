"""OIS Football Market Intelligence domain.

Deterministic market translation, web normalization, settlement, evaluation and
attribution primitives. Execution, policy, persistence and promotion remain owned
by OIS platform services.
"""

from .coverage import BookmakerMarketCoverage, build_market_coverage
from .evaluation import evaluate_market_event
from .integration import translate_market
from .market_catalog import MarketDefinition, MarketFamily, catalog, normalize_market_key, provider_market_mapping
from .markets import MarketType, Selection
from .schemas import MarketEvent, MarketOutcome
from .settlement import settle_market
from .web_adapters import FOOTBALL_DATA, ODDS_API, SPORTMONKS, fetch_and_parse, parse_football_data_matches, parse_odds_api, parse_sportmonks_odds
from .web_normalization import assert_temporal_integrity, check_provider_health, normalize_observations
from .web_sources import MatchObservation, NormalizationResult, OddsObservation, ProviderHealth, WebObservation, WebSource, WebTransport

__all__ = [
    "BookmakerMarketCoverage",
    "FOOTBALL_DATA",
    "ODDS_API",
    "SPORTMONKS",
    "MatchObservation",
    "MarketDefinition",
    "MarketEvent",
    "MarketFamily",
    "MarketOutcome",
    "MarketType",
    "NormalizationResult",
    "OddsObservation",
    "ProviderHealth",
    "Selection",
    "WebObservation",
    "WebSource",
    "WebTransport",
    "assert_temporal_integrity",
    "build_market_coverage",
    "catalog",
    "check_provider_health",
    "evaluate_market_event",
    "fetch_and_parse",
    "normalize_market_key",
    "normalize_observations",
    "parse_football_data_matches",
    "parse_odds_api",
    "parse_sportmonks_odds",
    "provider_market_mapping",
    "settle_market",
    "translate_market",
]
