"""OIS runtime intelligence-fabric contracts and deterministic boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ExecutionTarget:
    """Explicit resolved target consumed by the execution plane."""

    target_id: str
    action_name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Explicit validation result returned before execution proceeds."""

    is_valid: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryDecision:
    """Explicit recovery decision; failures are never silently retried."""

    action: Literal["retry", "escalate"]
    reason: str
    retry_count: int = 0
    max_retries: int = 3


@dataclass(frozen=True)
class StructuredEvent:
    """Structured observability event."""

    event_id: str
    event_type: str
    plane: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


class IntelligenceFabricProvider(Protocol):
    """Runtime contract for intelligence-fabric capability providers."""

    def resolve_target(self, target_id: str) -> ExecutionTarget:
        """Resolve an explicitly registered target."""
        ...

    def validate_execution(self, target: ExecutionTarget) -> ValidationResult:
        """Validate a resolved target before execution."""
        ...

    def evaluate_recovery(
        self, target: ExecutionTarget, error: Exception, attempt: int
    ) -> RecoveryDecision:
        """Return an explicit recovery decision."""
        ...


class DefaultIntelligenceFabric:
    """Small deterministic runtime boundary for the intelligence fabrics."""

    def __init__(self, provider_id: str = "default_fabric") -> None:
        self.provider_id = provider_id

    def validate_target(self, target: ExecutionTarget) -> ValidationResult:
        """Validate the minimum fields required for execution."""
        if not target.target_id or not target.action_name:
            return ValidationResult(
                is_valid=False,
                reason="target_id and action_name must be non-empty strings",
            )
        return ValidationResult(is_valid=True, reason="target configuration is valid")

    def handle_failure(
        self, target: ExecutionTarget, error: Exception, attempt: int
    ) -> RecoveryDecision:
        """Choose retry until the bounded limit, then escalate."""
        if attempt < 3:
            return RecoveryDecision(
                action="retry",
                reason=(
                    f"Failure for {target.target_id}: {error}; "
                    f"retrying attempt {attempt + 1}"
                ),
                retry_count=attempt,
            )
        return RecoveryDecision(
            action="escalate",
            reason=(
                f"Exceeded maximum retries ({attempt}) for "
                f"{target.target_id}: {error}"
            ),
            retry_count=attempt,
        )

    def create_telemetry_event(
        self, event_type: str, details: dict[str, Any]
    ) -> StructuredEvent:
        """Create an append-only-style structured event for observability."""
        return StructuredEvent(
            event_id=f"evt_{datetime.now(timezone.utc).timestamp()}",
            event_type=event_type,
            plane="IntelligenceFabric",
            details=details,
        )
