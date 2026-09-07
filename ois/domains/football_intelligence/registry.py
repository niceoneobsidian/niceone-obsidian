"""Football domain manifest for integration with the existing OIS registries."""

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
class FootballAgentSpec:
    agent_id: str
    role: str
    capabilities: tuple[str, ...]


FOOTBALL_CAPABILITIES: tuple[DomainCapability, ...] = (
    DomainCapability(
        "football.ingest",
        "Ingest canonical football data",
        "FootballDataBatch",
        "FootballDataBatch",
    ),
    DomainCapability(
        "football.team_state", "Build team strength state", "MatchHistory", "TeamSnapshot"
    ),
    DomainCapability(
        "football.player_state", "Build player availability/state", "PlayerDataBatch", "PlayerState"
    ),
    DomainCapability(
        "football.features", "Build leakage-safe match features", "MatchState", "FeatureVector"
    ),
    DomainCapability(
        "football.predict_1x2",
        "Predict calibrated 1X2 probabilities",
        "MatchState",
        "FootballPrediction",
    ),
    DomainCapability(
        "football.simulate",
        "Simulate score/outcome distributions",
        "MatchState",
        "SimulationResult",
    ),
    DomainCapability(
        "football.tactical_analysis", "Analyze tactical matchup", "MatchState", "TacticalAnalysis"
    ),
    DomainCapability(
        "football.live_update",
        "Update prediction from live state",
        "LiveMatchState",
        "FootballPrediction",
    ),
    DomainCapability(
        "football.calibrate",
        "Evaluate probability calibration",
        "PredictionSet",
        "CalibrationReport",
    ),
    DomainCapability(
        "football.backtest", "Run walk-forward backtests", "DatasetSpec", "BacktestReport"
    ),
    DomainCapability(
        "football.abstain",
        "Decide whether confidence supports publication",
        "FootballPrediction",
        "AbstentionDecision",
    ),
    DomainCapability(
        "football.research",
        "Produce evidence-backed football research",
        "FootballResearchQuery",
        "FootballResearchBrief",
    ),
)

FOOTBALL_AGENTS: tuple[FootballAgentSpec, ...] = (
    FootballAgentSpec(
        "football.data_agent", "Football data ingestion and validation", ("football.ingest",)
    ),
    FootballAgentSpec(
        "football.team_agent",
        "Team strength intelligence",
        ("football.team_state", "football.features"),
    ),
    FootballAgentSpec(
        "football.player_agent", "Player and lineup intelligence", ("football.player_state",)
    ),
    FootballAgentSpec(
        "football.tactical_agent", "Tactical matchup intelligence", ("football.tactical_analysis",)
    ),
    FootballAgentSpec(
        "football.prediction_agent",
        "Statistical and ensemble prediction",
        ("football.predict_1x2", "football.simulate"),
    ),
    FootballAgentSpec("football.live_agent", "Live match intelligence", ("football.live_update",)),
    FootballAgentSpec(
        "football.evaluation_agent",
        "Calibration and walk-forward evaluation",
        ("football.calibrate", "football.backtest"),
    ),
    FootballAgentSpec(
        "football.supervisor",
        "Supervise football domain workflows",
        tuple(c.capability_id for c in FOOTBALL_CAPABILITIES),
    ),
)


def manifest() -> dict[str, list[dict[str, Any]]]:
    return {
        "domain": "football_intelligence",
        "capabilities": [c.__dict__.copy() for c in FOOTBALL_CAPABILITIES],
        "agents": [a.__dict__.copy() for a in FOOTBALL_AGENTS],
        "workflows": [
            {"workflow_id": "football.predict", "version": 1},
            {"workflow_id": "football.backtest", "version": 1},
            {"workflow_id": "football.live_prediction", "version": 1},
        ],
        "model_registry_namespace": "football",
        "connector_contract": "FootballDataConnector",
    }
