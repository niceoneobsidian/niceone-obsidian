"""Deterministic recovery conformance scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecoveryAction(StrEnum):
    RETRY = "retry"
    FALLBACK = "fallback"
    REPLAN = "replan"
    ESCALATE = "escalate"
    TERMINATE = "terminate"


@dataclass(frozen=True)
class RecoveryCase:
    case_id: str
    fault: str
    expected: RecoveryAction
    max_attempts: int = 2


RECOVERY_CASES = (
    RecoveryCase("RC-01", "timeout", RecoveryAction.RETRY),
    RecoveryCase("RC-02", "transient_tool_failure", RecoveryAction.RETRY),
    RecoveryCase("RC-03", "primary_provider_unavailable", RecoveryAction.FALLBACK),
    RecoveryCase("RC-04", "invalid_output_schema", RecoveryAction.REPLAN),
    RecoveryCase("RC-05", "credential_expired", RecoveryAction.ESCALATE),
    RecoveryCase("RC-06", "policy_denied", RecoveryAction.TERMINATE, 1),
    RecoveryCase("RC-07", "tenant_mismatch", RecoveryAction.TERMINATE, 1),
    RecoveryCase("RC-08", "duplicate_delivery", RecoveryAction.TERMINATE, 1),
    RecoveryCase("RC-09", "provider_rate_limit", RecoveryAction.RETRY),
    RecoveryCase("RC-10", "malformed_event", RecoveryAction.TERMINATE, 1),
    RecoveryCase("RC-11", "checkpoint_write_failure", RecoveryAction.ESCALATE),
    RecoveryCase("RC-12", "unknown_fault", RecoveryAction.ESCALATE),
)
