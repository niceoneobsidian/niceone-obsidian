"""Production control-plane services: durable state, policy, recovery and evidence."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class RecoveryAction(StrEnum):
    RETRY = "retry"
    FALLBACK = "fallback"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    action: RecoveryAction
    attempt: int
    reason: str


@dataclass(slots=True)
class ExecutionRecord:
    execution_id: str
    capability: str
    state: str = "proposed"
    attempts: int = 0
    output: Any = None
    error: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)


class EvidenceLedger:
    """Append-only, hash-chained evidence for one execution stream."""
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def append(self, event_id: str, event: dict[str, Any]) -> str:
        if event_id in self._ids:
            raise ValueError(f"duplicate evidence id: {event_id}")
        previous = self._events[-1]["hash"] if self._events else "GENESIS"
        payload = {"id": event_id, "event": event, "previous_hash": previous}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        record = {**payload, "hash": digest}
        self._events.append(record)
        self._ids.add(event_id)
        return digest

    def verify(self) -> bool:
        previous = "GENESIS"
        for record in self._events:
            payload = {"id": record["id"], "event": record["event"], "previous_hash": previous}
            expected = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
            if expected != record["hash"]:
                return False
            previous = record["hash"]
        return True

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)


class RecoveryEngine:
    """Bounded, safety-aware recovery policy; permission failures never retry."""
    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def decide(self, error_class: str, attempt: int, *, fallback_available: bool = False) -> RecoveryDecision:
        if error_class in {"permission_denied", "policy_denied", "safety_failure"}:
            return RecoveryDecision(RecoveryAction.ESCALATE, attempt, "safety/authority failure")
        if error_class == "tool_unavailable" and fallback_available:
            return RecoveryDecision(RecoveryAction.FALLBACK, attempt, "primary capability unavailable")
        if error_class in {"invalid_output", "schema_error"}:
            return RecoveryDecision(RecoveryAction.REPLAN, attempt, "output contract failed")
        if attempt < self.max_retries:
            return RecoveryDecision(RecoveryAction.RETRY, attempt + 1, "bounded transient recovery")
        return RecoveryDecision(RecoveryAction.ESCALATE, attempt, "recovery budget exhausted")


class IdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._results.get(key)

    def put(self, key: str, result: Any) -> None:
        self._results[key] = result


@dataclass(frozen=True, slots=True)
class SecurityContext:
    actor: str
    tenant_id: str = "personal"
    permissions: frozenset[str] = frozenset()


class SecurityGate:
    """Defense-in-depth authorization boundary before capability execution."""
    def authorize(self, context: SecurityContext, required_permissions: set[str], risk: str) -> tuple[bool, str]:
        if not required_permissions.issubset(context.permissions):
            return False, "required permission missing"
        if risk == "critical" and "approve:critical" not in context.permissions:
            return False, "critical approval missing"
        return True, "authorized"


class E2ERunner:
    """Deterministic E2E harness used by CI and local conformance tests."""
    def __init__(self, execute: Callable[[ExecutionRecord], Any], *, ledger: EvidenceLedger | None = None) -> None:
        self.execute = execute
        self.ledger = ledger or EvidenceLedger()
        self.recovery = RecoveryEngine()
        self.idempotency = IdempotencyStore()

    def run(self, record: ExecutionRecord, *, idempotency_key: str) -> ExecutionRecord:
        cached = self.idempotency.get(idempotency_key)
        if cached is not None:
            record.output = cached
            record.state = "succeeded"
            return record
        record.state = "running"
        started = time.time()
        try:
            record.output = self.execute(record)
            record.state = "succeeded"
            self.idempotency.put(idempotency_key, record.output)
            self.ledger.append(f"{record.execution_id}:success", {"state": record.state, "duration_ms": round((time.time()-started)*1000)})
            return record
        except PermissionError as exc:
            record.state, record.error = "escalated", str(exc)
            self.ledger.append(f"{record.execution_id}:permission", {"state": record.state, "error_class": "permission_denied"})
            return record
        except Exception as exc:  # noqa: BLE001 - boundary classifies unknown provider failures
            record.attempts += 1
            decision = self.recovery.decide("transient", record.attempts)
            record.error = str(exc)
            if decision.action == RecoveryAction.RETRY:
                return self.run(record, idempotency_key=idempotency_key)
            record.state = "escalated"
            self.ledger.append(f"{record.execution_id}:recovery", {"action": decision.action.value, "attempt": record.attempts})
            return record
