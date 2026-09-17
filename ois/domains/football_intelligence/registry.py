"""Football domain manifest for the authoritative OIS registries."""
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

FOOTBALL_CAPABILITIES = (
    DomainCapability("football.contract", "Validate F0 canonical football contract", "FootballRequest", "FootballContractReport"),
    DomainCapability("football.ingest", "Ingest live fixtures and results", "FixtureQuery", "FootballDataBatch"),
    DomainCapability("football.history", "Persist and retrieve historical football data", "FootballDataBatch", "HistoricalDataset"),
    DomainCapability("football.team_state", "Build chronological team strength state", "MatchHistory", "TeamSnapshot"),
    DomainCapability("football.xg", "Estimate expected goals and score distribution", "MatchState", "XGForecast"),
    DomainCapability("football.calibrate", "Fit and evaluate probability calibration", "PredictionSet", "CalibrationReport"),
    DomainCapability("football.market", "Normalize odds and calculate market edge", "OddsSnapshot", "MarketIntelligence"),
    DomainCapability("football.backtest", "Run chronological backtests", "DatasetSpec", "BacktestReport"),
    DomainCapability("football.walk_forward", "Run leakage-safe walk-forward evaluation", "DatasetSpec", "WalkForwardReport"),
    DomainCapability("football.evidence", "Emit football evidence events to OIS", "FootballEvidence", "EvidenceEvent"),
    DomainCapability("football.predict_1x2", "Produce governed football probabilities", "MatchState", "FootballPrediction"),
    DomainCapability("football.live_update", "Update live football intelligence", "LiveMatchState", "LiveFootballState"),
    DomainCapability("football.dashboard", "Expose read-only football intelligence state", "DashboardQuery", "DashboardSnapshot"),
    DomainCapability("football.evolve", "Propose reversible model evolution", "EvaluationDelta", "EvolutionProposal", requires_approval=True),
)

FOOTBALL_AGENTS = (
    FootballAgentSpec("football.data_agent", "Football data ingestion and validation", ("football.ingest", "football.history")),
    FootballAgentSpec("football.team_agent", "Team strength and xG intelligence", ("football.team_state", "football.xg")),
    FootballAgentSpec("football.market_agent", "Odds and market intelligence", ("football.market",)),
    FootballAgentSpec("football.evaluation_agent", "Calibration, backtest and walk-forward evaluation", ("football.calibrate", "football.backtest", "football.walk_forward")),
    FootballAgentSpec("football.supervisor", "Supervise football domain workflows", tuple(c.capability_id for c in FOOTBALL_CAPABILITIES)),
)

def manifest() -> dict[str, Any]:
    return {
        "domain": "football_intelligence",
        "version": "f0-f12-v1",
        "capabilities": [c.__dict__.copy() for c in FOOTBALL_CAPABILITIES],
        "agents": [a.__dict__.copy() for a in FOOTBALL_AGENTS],
        "workflows": [
            {"workflow_id": "football.ingest", "version": 1},
            {"workflow_id": "football.predict", "version": 1},
            {"workflow_id": "football.evaluate", "version": 1},
            {"workflow_id": "football.live", "version": 1},
            {"workflow_id": "football.evolve", "version": 1, "requires_approval": True},
        ],
        "model_registry_namespace": "football",
        "connector_contract": "FootballDataConnector",
        "evidence_contract": "OIS Evidence Ledger",
    }
