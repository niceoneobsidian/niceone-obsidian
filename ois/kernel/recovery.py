from __future__ import annotations

from dataclasses import dataclass

from .state import ExecutionContext
from .types import ExecutionStatus, FailureClass


class RecoveryError(Exception):
    """Base recovery error."""


class RetryLimitExceeded(RecoveryError):
    """Raised when the retry policy is exhausted."""


@dataclass(frozen=True)
class RecoveryDecision:
    failure: FailureClass
    action: str
    retry_allowed: bool
    terminal: bool
    reason: str


class RecoveryPolicy:
    """
    Conservative deterministic recovery policy.

    Recovery actions:
    - retry
    - correct
    - fallback
    - replan
    - recover
    - escalate
    - stop
    """

    def __init__(
        self,
        max_retries: int = 2,
        max_recovery_attempts: int = 3,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        if max_recovery_attempts < 0:
            raise ValueError("max_recovery_attempts must be >= 0")

        self.max_retries = max_retries
        self.max_recovery_attempts = max_recovery_attempts

    def classify(
        self,
        failure: FailureClass,
        context: ExecutionContext,
    ) -> RecoveryDecision:
        if failure == FailureClass.TRANSIENT:
            allowed = context.retry_count < self.max_retries

            return RecoveryDecision(
                failure=failure,
                action="retry" if allowed else "escalate",
                retry_allowed=allowed,
                terminal=not allowed,
                reason=("Transient failure is retryable." if allowed else "Transient retry limit exhausted."),
            )

        if failure == FailureClass.PARAMETER:
            return RecoveryDecision(
                failure=failure,
                action="correct",
                retry_allowed=False,
                terminal=False,
                reason="Parameters require correction before retry.",
            )

        if failure == FailureClass.TOOL:
            return RecoveryDecision(
                failure=failure,
                action="fallback",
                retry_allowed=False,
                terminal=False,
                reason="Tool failure should use an alternative capability.",
            )

        if failure == FailureClass.PLAN:
            return RecoveryDecision(
                failure=failure,
                action="replan",
                retry_allowed=False,
                terminal=False,
                reason="Plan failure requires replanning.",
            )

        if failure == FailureClass.STATE:
            allowed = context.recovery_attempts < self.max_recovery_attempts

            return RecoveryDecision(
                failure=failure,
                action="recover" if allowed else "escalate",
                retry_allowed=False,
                terminal=not allowed,
                reason=("State recovery is permitted." if allowed else "State recovery limit exhausted."),
            )

        if failure == FailureClass.PERMISSION:
            return RecoveryDecision(
                failure=failure,
                action="escalate",
                retry_allowed=False,
                terminal=False,
                reason="Permission failures require escalation.",
            )

        if failure == FailureClass.SAFETY:
            return RecoveryDecision(
                failure=failure,
                action="stop",
                retry_allowed=False,
                terminal=True,
                reason="Safety failures must terminate execution.",
            )

        return RecoveryDecision(
            failure=FailureClass.UNKNOWN,
            action="escalate",
            retry_allowed=False,
            terminal=False,
            reason="Unknown failure requires escalation.",
        )

    def apply(
        self,
        context: ExecutionContext,
        failure: FailureClass,
    ) -> RecoveryDecision:
        decision = self.classify(failure, context)

        context.last_failure = failure
        context.error = {
            "failure_class": failure.value,
            "recovery_action": decision.action,
            "reason": decision.reason,
        }

        if decision.action == "retry":
            context.retry_count += 1
            context.set_status(ExecutionStatus.RECOVERING)

        elif decision.action == "recover":
            context.recovery_attempts += 1
            context.set_status(ExecutionStatus.RECOVERING)

        elif decision.action == "replan":
            context.recovery_attempts += 1
            context.set_status(ExecutionStatus.REPLANNING)

        elif decision.action == "escalate":
            context.set_status(ExecutionStatus.ESCALATED)

        elif decision.action == "stop":
            context.set_status(ExecutionStatus.STOPPED)

        return decision
