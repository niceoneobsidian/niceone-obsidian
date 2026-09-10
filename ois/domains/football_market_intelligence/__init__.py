"""OIS Football Market Intelligence domain.

Deterministic market translation, pricing, value detection, backtesting, web
normalization, settlement, evaluation and attribution primitives. Execution,
policy, persistence and promotion remain owned by OIS platform services.
"""

from .backtest import BacktestBet, BacktestConfig, BacktestResult, run_backtest
from .coverage import BookmakerMarketCoverage, build_market_coverage
from .engine import MarketSignal, generate_value_signals
from .evaluation import evaluate_market_event
from .integration import translate_market
from .market_catalog import MarketDefinition, MarketFamily, catalog, normalize_market_key, provider_market_mapping
from .markets import MarketType, Selection
from .pricing import FairMarket, MarketPrice, best_prices, closing_line_value, devig, edge, expected_value, kelly_fraction
from .schemas import MarketEvent, MarketOutcome
from .settlement import settle_market
from .web_adapters import FOOTBALL_DATA, ODDS_API, SPORTMONKS, fetch_and_parse, parse_football_data_matches, parse_odds_api, parse_sportmonks_odds
from .web_normalization import assert_temporal_integrity, check_provider_health, normalize_observations
from .web_sources import MatchObservation, NormalizationResult, OddsObservation, ProviderHealth, WebObservation, WebSource, WebTransport

__all__ = [
    "BacktestBet", "BacktestConfig", "BacktestResult", "BookmakerMarketCoverage",
    "FairMarket", "FOOTBALL_DATA", "MarketDefinition", "MarketEvent", "MarketFamily",
    "MarketOutcome", "MarketPrice", "MarketSignal", "MarketType", "MatchObservation",
    "NormalizationResult", "ODDS_API", "OddsObservation", "ProviderHealth", "SPORTMONKS",
    "Selection", "WebObservation", "WebSource", "WebTransport", "assert_temporal_integrity",
    "best_prices", "build_market_coverage", "catalog", "check_provider_health",
    "closing_line_value", "devig", "edge", "evaluate_market_event", "expected_value",
    "fetch_and_parse", "generate_value_signals", "kelly_fraction", "normalize_market_key",
    "normalize_observations", "parse_football_data_matches", "parse_odds_api",
    "parse_sportmonks_odds", "provider_market_mapping", "run_backtest", "settle_market",
    "translate_market",
]
