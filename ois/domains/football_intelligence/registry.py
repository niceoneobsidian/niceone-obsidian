"""Football domain manifest for the authoritative OIS registries."""
# fmt: off
# ruff: noqa: E501
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

FOOTBALL_CAPABILITIES: tuple[DomainCapability, ...] = (
    DomainCapability("football.ingest", "Ingest canonical football data", "FootballDataBatch", "FootballDataBatch"),
    DomainCapability("football.live_feed", "Collect live multi-provider match state", "FeedQuery", "ReconciledMatchSet"),
    DomainCapability("football.match_stats", "Collect match team statistics", "MatchId", "TeamStatFeed"),
    DomainCapability("football.player_stats", "Collect match player statistics", "MatchId", "PlayerStatFeed"),
    DomainCapability("football.team_state", "Build team strength state", "MatchHistory", "TeamSnapshot"),
    DomainCapability("football.player_state", "Build player availability/state", "PlayerDataBatch", "PlayerState"),
    DomainCapability("football.features", "Build leakage-safe match features", "MatchState", "FeatureVector"),
    DomainCapability("football.predict_1x2", "Predict calibrated 1X2 probabilities", "MatchState", "FootballPrediction"),
    DomainCapability("football.market_goals", "Price goal totals, BTTS and team-goal markets", "MatchState", "MarketPrediction"),
    DomainCapability("football.market_result", "Price 1X2, DNB and double chance", "MatchState", "MarketPrediction"),
    DomainCapability("football.market_corners", "Price corner totals and handicaps", "CornerFeatureVector", "MarketPrediction"),
    DomainCapability("football.market_cards", "Price card totals and player-card markets", "CardFeatureVector", "MarketPrediction"),
    DomainCapability("football.market_shots", "Price player shots and shots-on-target", "ShotFeatureVector", "MarketPrediction"),
    DomainCapability("football.market_player_goals", "Price anytime-scorer probabilities", "PlayerFeatureVector", "MarketProbability"),
    DomainCapability("football.market_live", "Price live totals, next-goal and live handicap markets", "LiveMatchState", "MarketPrediction"),
    DomainCapability("football.simulate", "Simulate score/outcome distributions", "MatchState", "SimulationResult"),
    DomainCapability("football.tactical_analysis", "Analyze tactical matchup", "MatchState", "TacticalAnalysis"),
    DomainCapability("football.live_update", "Update prediction from live state", "LiveMatchState", "FootballPrediction"),
    DomainCapability("football.calibrate", "Evaluate probability calibration", "PredictionSet", "CalibrationReport"),
    DomainCapability("football.backtest", "Run walk-forward backtests", "DatasetSpec", "BacktestReport"),
    DomainCapability("football.abstain", "Decide whether confidence supports publication", "FootballPrediction", "AbstentionDecision"),
    DomainCapability("football.research", "Produce evidence-backed football research", "FootballResearchQuery", "FootballResearchBrief"),
)

FOOTBALL_AGENTS: tuple[FootballAgentSpec, ...] = (
    FootballAgentSpec("football.data_agent", "Football data ingestion and validation", ("football.ingest", "football.live_feed", "football.match_stats", "football.player_stats")),
    FootballAgentSpec("football.team_agent", "Team strength intelligence", ("football.team_state", "football.features")),
    FootballAgentSpec("football.player_agent", "Player and lineup intelligence", ("football.player_state", "football.player_stats", "football.market_shots", "football.market_player_goals")),
    FootballAgentSpec("football.tactical_agent", "Tactical matchup intelligence", ("football.tactical_analysis",)),
    FootballAgentSpec("football.prediction_agent", "Market-specific statistical prediction", ("football.predict_1x2", "football.market_goals", "football.market_result", "football.market_corners", "football.market_cards", "football.market_shots", "football.market_player_goals")),
    FootballAgentSpec("football.live_agent", "Live match intelligence", ("football.live_update", "football.live_feed", "football.market_live")),
    FootballAgentSpec("football.evaluation_agent", "Calibration and walk-forward evaluation", ("football.calibrate", "football.backtest")),
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
            {"workflow_id": "football.market_pricing", "version": 1},
            {"workflow_id": "football.backtest", "version": 1},
            {"workflow_id": "football.live_prediction", "version": 1},
            {"workflow_id": "football.feed_snapshot", "version": 1},
        ],
        "model_registry_namespace": "football",
        "connector_contract": "FootballDataConnector",
        "evidence_contract": "OIS Evidence Ledger",
    }
