"""Evidence Runtime v1 execution gate."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from .core import (
    AdmissibilityDecision,
    EvidenceEnvelope,
    EvidenceLedgerV1,
    ExecutionReceipt,
    OutcomeReceipt,
    SingleUseAuthorization,
    authorization_for,
    canonical_digest,
)


class EvidenceRuntimeV1:
    """Small, deterministic runtime boundary for governed vertical slices.

    Models/agents can propose actions. This class alone decides whether an action
    may cross the execution boundary, and every authorization is single-use and
    digest-bound to the exact action, evidence set and policy snapshot.
    """

    def __init__(self, ledger: EvidenceLedgerV1 | None = None) -> None:
        self.ledger = ledger or EvidenceLedgerV1()
        self._evidence: dict[str, EvidenceEnvelope] = {}
        self._authorizations: dict[str, SingleUseAuthorization] = {}

    def ingest(
        self,
        run_id: UUID,
        *,
        evidence_type: str,
        source_id: str,
        payload: Any,
        provenance: Mapping[str, Any] | None = None,
        parent_evidence_ids: tuple[str, ...] = (),
        trust_class: str = "observation",
        observed_at: datetime | None = None,
    ) -> EvidenceEnvelope:
        evidence = EvidenceEnvelope.create(
            run_id,
            evidence_type=evidence_type,
            source_id=source_id,
            payload=payload,
            provenance=provenance,
            parent_evidence_ids=parent_evidence_ids,
            trust_class=trust_class,
            observed_at=observed_at,
        )
        self._evidence[evidence.evidence_id] = evidence
        self.ledger.append(run_id, "EVIDENCE_RECEIVED", evidence.as_record())
        return evidence

    def admissible(
        self,
        run_id: UUID,
        *,
        action: Mapping[str, Any],
        evidence_ids: tuple[str, ...],
        policy: Mapping[str, Any],
        authorization_root: Mapping[str, Any],
        max_age_seconds: float | None = None,
    ) -> AdmissibilityDecision:
        reasons: list[str] = []
        missing = [evidence_id for evidence_id in evidence_ids if evidence_id not in self._evidence]
        if missing:
            reasons.append("missing_evidence")

        action_digest = canonical_digest(action)
        root_actions = authorization_root.get("allowed_actions", ())
        allowed_action_digests = {canonical_digest(item) for item in root_actions if isinstance(item, Mapping)}
        if action_digest not in allowed_action_digests:
            reasons.append("authorization_root_mismatch")

        evidence = [self._evidence[evidence_id] for evidence_id in evidence_ids if evidence_id in self._evidence]
        if max_age_seconds is not None:
            now = datetime.now(UTC)
            if any((now - item.observed_at).total_seconds() > max_age_seconds for item in evidence):
                reasons.append("stale_evidence")

        if policy.get("deny", False):
            reasons.append("policy_denied")

        decision = AdmissibilityDecision(
            allowed=not reasons,
            decision_id=f"DEC-{uuid4().hex}",
            action_digest=action_digest,
            evidence_digest=canonical_digest(sorted(evidence_ids)),
            policy_digest=canonical_digest(policy),
            reason_codes=tuple(reasons),
        )
        self.ledger.append(
            run_id,
            "ACTION_ADMISSIBILITY_EVALUATED",
            {"decision": decision.allowed, "decision_id": decision.decision_id, "reasons": reasons},
        )
        return decision

    def authorize(
        self,
        run_id: UUID,
        *,
        decision: AdmissibilityDecision,
        policy: Mapping[str, Any],
        ttl_seconds: int = 60,
    ) -> SingleUseAuthorization:
        if not decision.allowed:
            raise PermissionError("action_not_admissible")
        authorization = authorization_for(
            run_id,
            {"action_digest": decision.action_digest},
            (decision.evidence_digest,),
            policy,
            ttl_seconds=ttl_seconds,
        )
        # Bind the authorization to the decision digest exactly; no re-interpretation later.
        self._authorizations[authorization.authorization_id] = authorization
        self.ledger.append(
            run_id,
            "ACTION_AUTHORIZED",
            {"authorization_id": authorization.authorization_id, "action_digest": decision.action_digest},
        )
        return authorization

    def execute(
        self,
        run_id: UUID,
        *,
        authorization: SingleUseAuthorization,
        action: Mapping[str, Any],
        tool: str,
        executor: Callable[[Mapping[str, Any]], Any],
        evidence_ids: tuple[str, ...],
    ) -> tuple[ExecutionReceipt, Any]:
        current = self._authorizations.get(authorization.authorization_id)
        if current is None:
            raise PermissionError("unknown_authorization")
        if canonical_digest(action) != current.action_digest:
            raise PermissionError("action_digest_mismatch")
        if canonical_digest(sorted(evidence_ids)) != canonical_digest([current.evidence_digest]):
            # The v1 contract deliberately rejects re-binding an authorization to another evidence set.
            raise PermissionError("evidence_digest_mismatch")
        consumed = current.consume()
        self._authorizations[consumed.authorization_id] = consumed

        started = datetime.now(UTC)
        self.ledger.append(run_id, "ACTION_EXECUTION_STARTED", {"tool": tool})
        try:
            output = executor(action)
        except Exception as exc:
            self.ledger.append(run_id, "ACTION_EXECUTION_FAILED", {"error_type": type(exc).__name__})
            raise
        completed = datetime.now(UTC)
        receipt = ExecutionReceipt(
            execution_id=f"EXEC-{uuid4().hex}",
            authorization_id=consumed.authorization_id,
            action_digest=consumed.action_digest,
            tool=tool,
            status="succeeded",
            output_digest=canonical_digest(output),
            started_at=started,
            completed_at=completed,
            evidence_ids=evidence_ids,
        )
        self.ledger.append(run_id, "ACTION_EXECUTED", {"execution_id": receipt.execution_id, "output_digest": receipt.output_digest})
        return receipt, output

    def verify_outcome(
        self,
        run_id: UUID,
        *,
        outcome: Mapping[str, Any],
        expected: Mapping[str, Any],
        evidence_ids: tuple[str, ...],
    ) -> OutcomeReceipt:
        verified = dict(outcome) == dict(expected)
        receipt = OutcomeReceipt(
            outcome_id=f"OUT-{uuid4().hex}",
            run_id=run_id,
            outcome_digest=canonical_digest(outcome),
            verified=verified,
            verification_reason="exact_match" if verified else "outcome_mismatch",
            evidence_ids=evidence_ids,
        )
        self.ledger.append(
            run_id,
            "OUTCOME_VERIFIED" if verified else "OUTCOME_VERIFICATION_FAILED",
            {"outcome_id": receipt.outcome_id, "verified": verified},
        )
        return receipt
