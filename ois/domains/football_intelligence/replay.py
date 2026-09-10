"""Evidence-gated Football Intelligence replay vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from ois.runtime.evidence import EvidenceRuntimeV1

from .evaluation import CalibrationReport, evaluate_predictions
from .integration import predict_match
from .schemas import FootballPrediction, MatchState


@dataclass(frozen=True)
class FootballReplayResult:
    run_id: UUID
    prediction: FootballPrediction
    evaluation: CalibrationReport
    outcome_verified: bool
    execution_id: str
    authorization_id: str
    evidence_ids: tuple[str, ...]


class FootballReplay:
    """Run one historical Football prediction through the governed runtime."""

    def __init__(self, runtime: EvidenceRuntimeV1 | None = None) -> None:
        self.runtime = runtime or EvidenceRuntimeV1()

    def run(
        self,
        match: MatchState,
        *,
        actual_outcome: str,
        source_id: str = "football.replay.fixture",
        max_evidence_age_seconds: float | None = None,
    ) -> FootballReplayResult:
        run_id = uuid4()
        match_payload = match.model_dump(mode="json")
        observed_at = datetime.now(UTC)
        evidence = self.runtime.ingest(
            run_id,
            evidence_type="football.match_state",
            source_id=source_id,
            payload=match_payload,
            provenance={
                "mode": "replay",
                "source_type": "fixture",
                "observed_at": observed_at.isoformat(),
            },
            observed_at=observed_at,
        )
        outcome_evidence = self.runtime.ingest(
            run_id,
            evidence_type="football.match_outcome",
            source_id=source_id,
            payload={"match_id": match.match_id, "outcome": actual_outcome},
            provenance={"mode": "replay", "source_type": "fixture"},
            observed_at=observed_at,
        )

        action: dict[str, Any] = {
            "capability": "football.replay.predict",
            "match_id": match.match_id,
            "ensemble_version": "football-ensemble-v1",
        }
        evidence_ids = (evidence.evidence_id,)
        policy = {"policy_id": "football-replay-v1", "deny": False, "mode": "replay"}
        authorization_root = {"allowed_actions": (action,)}
        decision = self.runtime.admissible(
            run_id,
            action=action,
            evidence_ids=evidence_ids,
            policy=policy,
            authorization_root=authorization_root,
            max_age_seconds=max_evidence_age_seconds,
        )
        authorization = self.runtime.authorize(
            run_id,
            decision=decision,
            action=action,
            evidence_ids=evidence_ids,
            policy=policy,
        )
        receipt, prediction = self.runtime.execute(
            run_id,
            authorization=authorization,
            action=action,
            tool="football_intelligence.predict_match",
            executor=lambda _: predict_match(match),
            evidence_ids=evidence_ids,
        )
        if not isinstance(prediction, FootballPrediction):
            raise TypeError("football prediction executor returned an invalid result")

        expected_outcome = {"match_id": match.match_id, "outcome": actual_outcome}
        outcome_receipt = self.runtime.verify_outcome(
            run_id,
            outcome=expected_outcome,
            expected=expected_outcome,
            evidence_ids=(outcome_evidence.evidence_id,),
        )
        report = evaluate_predictions([prediction], [actual_outcome])
        self.runtime.ledger.append(
            run_id,
            "FOOTBALL_REPLAY_MEASURED",
            {
                "match_id": match.match_id,
                "accuracy": report.accuracy,
                "brier": report.multiclass_brier,
                "log_loss": report.log_loss,
                "prediction": prediction.outcome,
            },
        )
        return FootballReplayResult(
            run_id=run_id,
            prediction=prediction,
            evaluation=report,
            outcome_verified=outcome_receipt.verified,
            execution_id=receipt.execution_id,
            authorization_id=authorization.authorization_id,
            evidence_ids=(evidence.evidence_id, outcome_evidence.evidence_id),
        )
