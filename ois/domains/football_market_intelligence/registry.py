"""Declarative registry manifest for Football Market Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DomainCapability:
    capability_id: str
    description: str
    input_contract: str
    output_contract: str
    side_effect: bool = False
    requires_approval: bool = False


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    role: str
    capabilities: tuple[str, ...]


CAPABILITIES: tuple[DomainCapability, ...] = (
    DomainCapability("football.market_translate", "Translate football prediction into an atomic market event", "FootballPrediction", "MarketEvent"),
    DomainCapability("football.market_price", "Compute fair probabilities, market edge and best available price", "ModelProbabilities+Odds", "MarketPricingReport"),
    DomainCapability("football.market_signal", "Generate ranked positive-value market signals", "ModelProbabilities+Odds+Thresholds", "MarketSignalSet"),
    DomainCapability("football.market_settle", "Deterministically settle a market event from final score", "MarketEvent+FinalScore", "MarketOutcome"),
    DomainCapability("football.market_evaluate", "Evaluate a settled market prediction", "MarketEvent+MarketOutcome", "MarketEvaluation"),
    DomainCapability("football.market_attribute", "Attribute market performance to prediction versions", "MarketEvaluationSet", "AttributionReport"),
    DomainCapability("football.market_record", "Record market events and outcomes through governed persistence", "MarketRecord", "MarketRecordReceipt", side_effect=True),
    DomainCapability("football.market_backtest", "Run chronological, leakage-safe market backtests", "MarketBacktestSpec", "MarketBacktestReport"),
    DomainCapability("football.market_web_ingest", "Ingest provider-neutral fixture, result and odds observations", "WebSource+URI", "NormalizationResult"),
    DomainCapability("football.market_web_health", "Check availability and latency of a registered market data provider", "WebSource+URI", "ProviderHealth"),
    DomainCapability("football.market_catalog", "Resolve provider market keys into canonical football market families", "ProviderMarketKey", "MarketDefinition"),
    DomainCapability("football.market_coverage", "Build observed bookmaker market coverage from normalized odds", "OddsObservationSet", "BookmakerMarketCoverage"),
)

AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec("football.market_agent", "Market taxonomy, pricing and value translation", ("football.market_translate", "football.market_catalog", "football.market_price", "football.market_signal")),
    AgentSpec("football.market_settlement_agent", "Deterministic market settlement", ("football.market_settle",)),
    AgentSpec("football.market_evaluation_agent", "Market evaluation and attribution", ("football.market_evaluate", "football.market_attribute")),
    AgentSpec("football.market_learning_agent", "Market backtesting and learning orchestration", ("football.market_backtest",)),
    AgentSpec("football.market_data_agent", "Provider ingestion, normalization, coverage and health", ("football.market_web_ingest", "football.market_web_health", "football.market_coverage")),
)


def manifest() -> dict[str, Any]:
    return {
        "domain": "football_market_intelligence",
        "capabilities": [c.__dict__.copy() for c in CAPABILITIES],
        "agents": [a.__dict__.copy() for a in AGENTS],
        "workflows": [
            {"workflow_id": "football.market_prediction", "version": 1},
            {"workflow_id": "football.market_evaluation", "version": 1},
            {"workflow_id": "football.market_backtest", "version": 1},
            {"workflow_id": "football.market_data_ingestion", "version": 1},
            {"workflow_id": "football.market_value_scan", "version": 1},
        ],
        "depends_on": "football_intelligence",
        "persistence_owner": "ois_platform",
    }
