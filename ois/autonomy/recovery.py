"""Failure recovery coordinator for autonomous workflow runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecoveryAction(StrEnum):
    RETRY = "retry"
    PAUSE = "pause"
    REPLAN = "replan"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass(frozen=True)
class RecoveryRecord:
    workflow_id: str
    event_id: str
    attempt: int
    action: RecoveryAction
    reason: str


class FailureRecovery:
    """Maps bounded failure classes to safe workflow recovery actions."""

    def __init__(self, max_retries: int = 2) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.max_retries = max_retries

    def decide(self, *, attempt: int, failure: str, safe_to_retry: bool = True) -> RecoveryRecord:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        if failure == "safety":
            action = RecoveryAction.STOP
        elif failure in {"permission", "approval"}:
            action = RecoveryAction.ESCALATE
        elif failure == "plan":
            action = RecoveryAction.REPLAN
        elif failure in {"transient", "timeout"} and safe_to_retry and attempt <= self.max_retries:
            action = RecoveryAction.RETRY
        elif failure == "state":
            action = RecoveryAction.PAUSE
        else:
            action = RecoveryAction.ESCALATE
        return RecoveryRecord("", "", attempt, action, f"recovery decision for {failure}")
