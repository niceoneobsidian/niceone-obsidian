"""F10-F11 governed agent/supervisor and read-only dashboard contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .origin import FootballSupervisor, PredictionRecord, FixtureRecord, dashboard_snapshot


@dataclass(frozen=True)
class AgentResponse:
    agent_id: str
    action: str
    capability: str
    answer: dict[str, Any]
    abstained: bool
    evidence_required: bool


class FootballAgent:
    """Read-only analyst agent. It proposes capability routing; OIS executes governed actions."""

    agent_id = "football.agent.v1"

    def __init__(self, supervisor: FootballSupervisor | None = None) -> None:
        self.supervisor = supervisor or FootballSupervisor()

    def handle(self, intent: str, validated: bool = False) -> AgentResponse:
        decision = self.supervisor.route(intent, validated=validated)
        if decision.action == "abstain":
            return AgentResponse(self.agent_id, decision.action, decision.capability, {"reason": decision.reason}, True, decision.evidence_required)
        return AgentResponse(self.agent_id, decision.action, decision.capability, {"intent": intent}, False, decision.evidence_required)


def build_dashboard_payload(
    fixtures: list[FixtureRecord], predictions: list[PredictionRecord], evaluated: int, model_version: str, validation_status: str
) -> dict[str, Any]:
    snapshot = dashboard_snapshot(fixtures, predictions, evaluated, model_version, validation_status)
    return {
        "generated_at": snapshot.generated_at.isoformat(),
        "domain": "football_intelligence",
        "read_only": True,
        "fixtures": snapshot.fixtures,
        "live": snapshot.live,
        "predictions": snapshot.predictions,
        "evaluated": snapshot.evaluated,
        "model_version": snapshot.model_version,
        "validation_status": snapshot.validation_status,
        "governance": {"external_side_effects": False, "promotion_requires_approval": True},
    }
