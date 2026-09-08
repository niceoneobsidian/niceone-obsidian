"""Recovery Conformance scenarios for OIS P0 execution safety."""
from __future__ import annotations

from dataclasses import dataclass

from .production import RecoveryAction, RecoveryEngine


@dataclass(frozen=True, slots=True)
class RecoveryScenario:
    id: str
    error_class: str
    attempt: int = 0
    fallback: bool = False
    expected: RecoveryAction = RecoveryAction.RETRY


SCENARIOS = (
    RecoveryScenario("RC-01", "timeout"),
    RecoveryScenario("RC-02", "transient"),
    RecoveryScenario("RC-03", "tool_unavailable", fallback=True, expected=RecoveryAction.FALLBACK),
    RecoveryScenario("RC-04", "invalid_output", expected=RecoveryAction.REPLAN),
    RecoveryScenario("RC-05", "permission_denied", expected=RecoveryAction.ESCALATE),
    RecoveryScenario("RC-06", "checkpoint_corrupt", attempt=3, expected=RecoveryAction.ESCALATE),
    RecoveryScenario("RC-07", "database_unavailable"),
    RecoveryScenario("RC-08", "process_crash"),
    RecoveryScenario("RC-09", "duplicate_execution"),
    RecoveryScenario("RC-10", "partial_side_effect", attempt=3, expected=RecoveryAction.ESCALATE),
    RecoveryScenario("RC-11", "cancelled", expected=RecoveryAction.ESCALATE),
    RecoveryScenario("RC-12", "recovery_exhausted", attempt=3, expected=RecoveryAction.ESCALATE),
)


def evaluate() -> dict[str, bool]:
    engine = RecoveryEngine(max_retries=3)
    return {
        s.id: engine.decide(s.error_class, s.attempt, fallback_available=s.fallback).action == s.expected
        for s in SCENARIOS
    }
