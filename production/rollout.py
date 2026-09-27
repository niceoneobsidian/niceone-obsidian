"""Controlled canary rollout orchestration over deployment and evidence primitives."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from production.control_plane import EvidenceLedger, ProductionControlPlane, Subject
from production.evolution import CanaryController, CanaryDecision, Measurement


@dataclass(frozen=True)
class RolloutResult:
    candidate: str
    state: str
    canary: CanaryDecision
    evidence_ids: tuple[str, ...]


class RolloutController:
    """Own the canary -> promote/rollback state transition."""

    def __init__(
        self,
        control_plane: ProductionControlPlane,
        canary: CanaryController,
        evidence: EvidenceLedger,
    ) -> None:
        self.control_plane = control_plane
        self.canary = canary
        self.evidence = evidence

    def evaluate_and_rollout(
        self,
        subject: Subject,
        candidate: str,
        environment: str,
        *,
        previous: str,
        traffic_percent: int,
        successes: int,
        total: int,
        latency_ms: float,
        measurements: Iterable[Measurement] = (),
    ) -> RolloutResult:
        execution_id = f"rollout:{candidate}:{environment}"
        self.evidence.append(
            execution_id,
            "rollout.canary.started",
            {"candidate": candidate, "traffic_percent": traffic_percent},
        )
        decision = self.canary.decide(
            candidate, traffic_percent, successes=successes, total=total, latency_ms=latency_ms
        )
        if not decision.passed:
            self.evidence.append(
                execution_id,
                "rollout.canary.failed",
                {"success_rate": decision.success_rate, "latency_ms": latency_ms},
            )
            rollback = self.control_plane.rollback(subject, previous, environment)
            ids = (
                tuple(e.event_id for e in self.evidence.events(execution_id))
                + rollback.evidence_ids
            )
            return RolloutResult(candidate, "ROLLED_BACK", decision, ids)
        self.evidence.append(
            execution_id,
            "rollout.canary.passed",
            {"success_rate": decision.success_rate, "latency_ms": latency_ms},
        )
        self.control_plane.activate(subject, candidate, environment, previous=previous)
        self.evidence.append(
            execution_id,
            "rollout.promoted",
            {"candidate": candidate, "measurements": [m.value for m in measurements]},
        )
        return RolloutResult(
            candidate,
            "PROMOTED",
            decision,
            tuple(e.event_id for e in self.evidence.events(execution_id)),
        )
