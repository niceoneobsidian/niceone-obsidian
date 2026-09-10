"""Deterministic evidence primitives for the OIS Evidence Runtime v1.

The runtime treats observations as data, never as authority. Authority is minted
only after an explicit admissibility decision and is bound to the exact action,
evidence set and policy snapshot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any, Mapping
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class EvidenceEnvelope:
    evidence_id: str
    run_id: UUID
    evidence_type: str
    source_id: str
    observed_at: datetime
    payload_digest: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    parent_evidence_ids: tuple[str, ...] = ()
    trust_class: str = "observation"
    schema_version: str = "evidence.v1"

    @classmethod
    def create(
        cls,
        run_id: UUID,
        *,
        evidence_type: str,
        source_id: str,
        payload: Any,
        provenance: Mapping[str, Any] | None = None,
        parent_evidence_ids: tuple[str, ...] = (),
        trust_class: str = "observation",
        observed_at: datetime | None = None,
    ) -> "EvidenceEnvelope":
        observed = observed_at or utc_now()
        payload_digest = canonical_digest(payload)
        identity = canonical_digest(
            {
                "run_id": str(run_id),
                "evidence_type": evidence_type,
                "source_id": source_id,
                "observed_at": observed.isoformat(),
                "payload_digest": payload_digest,
                "parent_evidence_ids": parent_evidence_ids,
            }
        )
        return cls(
            evidence_id=identity,
            run_id=run_id,
            evidence_type=evidence_type,
            source_id=source_id,
            observed_at=observed,
            payload_digest=payload_digest,
            provenance=provenance or {},
            parent_evidence_ids=parent_evidence_ids,
            trust_class=trust_class,
        )

    def as_record(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "run_id": str(self.run_id),
            "evidence_type": self.evidence_type,
            "source_id": self.source_id,
            "observed_at": self.observed_at.isoformat(),
            "payload_digest": self.payload_digest,
            "provenance": dict(self.provenance),
            "parent_evidence_ids": list(self.parent_evidence_ids),
            "trust_class": self.trust_class,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    event_type: str
    run_id: UUID
    payload: Mapping[str, Any]
    timestamp: datetime
    previous_digest: str
    event_digest: str


class EvidenceLedgerV1:
    """Thread-safe append-only hash-chain ledger."""

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._lock = RLock()

    def append(self, run_id: UUID, event_type: str, payload: Mapping[str, Any]) -> LedgerEvent:
        with self._lock:
            sequence = len(self._events) + 1
            previous = self._events[-1].event_digest if self._events else "0" * 64
            timestamp = utc_now()
            digest = canonical_digest(
                {
                    "sequence": sequence,
                    "event_type": event_type,
                    "run_id": str(run_id),
                    "payload": dict(payload),
                    "timestamp": timestamp.isoformat(),
                    "previous_digest": previous,
                }
            )
            event = LedgerEvent(sequence, event_type, run_id, dict(payload), timestamp, previous, digest)
            self._events.append(event)
            return event

    def list(self, run_id: UUID | None = None) -> tuple[LedgerEvent, ...]:
        with self._lock:
            if run_id is None:
                return tuple(self._events)
            return tuple(event for event in self._events if event.run_id == run_id)

    def verify(self) -> bool:
        with self._lock:
            previous = "0" * 64
            for expected_sequence, event in enumerate(self._events, start=1):
                if event.sequence != expected_sequence or event.previous_digest != previous:
                    return False
                expected = canonical_digest(
                    {
                        "sequence": event.sequence,
                        "event_type": event.event_type,
                        "run_id": str(event.run_id),
                        "payload": dict(event.payload),
                        "timestamp": event.timestamp.isoformat(),
                        "previous_digest": event.previous_digest,
                    }
                )
                if expected != event.event_digest:
                    return False
                previous = event.event_digest
            return True


@dataclass(frozen=True)
class AdmissibilityDecision:
    allowed: bool
    decision_id: str
    action_digest: str
    evidence_digest: str
    policy_digest: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SingleUseAuthorization:
    authorization_id: str
    run_id: UUID
    action_digest: str
    evidence_digest: str
    policy_digest: str
    issued_at: datetime
    expires_at: datetime
    consumed: bool = False

    def consume(self, now: datetime | None = None) -> "SingleUseAuthorization":
        if self.consumed:
            raise ValueError("authorization_replay")
        if (now or utc_now()) >= self.expires_at:
            raise ValueError("authorization_expired")
        return SingleUseAuthorization(
            self.authorization_id,
            self.run_id,
            self.action_digest,
            self.evidence_digest,
            self.policy_digest,
            self.issued_at,
            self.expires_at,
            True,
        )


@dataclass(frozen=True)
class ExecutionReceipt:
    execution_id: str
    authorization_id: str
    action_digest: str
    tool: str
    status: str
    output_digest: str
    started_at: datetime
    completed_at: datetime
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeReceipt:
    outcome_id: str
    run_id: UUID
    outcome_digest: str
    verified: bool
    verification_reason: str
    evidence_ids: tuple[str, ...]


def authorization_for(
    run_id: UUID,
    action: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
    policy: Mapping[str, Any],
    *,
    ttl_seconds: int = 60,
) -> SingleUseAuthorization:
    action_digest = canonical_digest(action)
    evidence_digest = canonical_digest(sorted(evidence_ids))
    policy_digest = canonical_digest(policy)
    issued = utc_now()
    return SingleUseAuthorization(
        authorization_id=f"AUTH-{uuid4().hex}",
        run_id=run_id,
        action_digest=action_digest,
        evidence_digest=evidence_digest,
        policy_digest=policy_digest,
        issued_at=issued,
        expires_at=issued + timedelta(seconds=ttl_seconds),
    )
