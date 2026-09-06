"""OIS Runtime Intelligence Fabrics plane contract and runtime interfaces."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ExecutionTarget:
    """Explicit resolved target for execution plane consumption."""

    target_id: str
    action_name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Explicit validation result returned by validation plane."""

    is_valid: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryDecision:
    """Explicit retry/escalate recovery decision without silent failures."""

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = field(default_factory=dict)


class IntelligenceFabricProvider(Protocol):
    """Runtime contract for Intelligence Fabric capability registration."""

    def resolve_target(self, target_id: str) -> ExecutionTarget: ...

    def validate_execution(self, target: ExecutionTarget) -> ValidationResult: ...

    def evaluate_recovery(
        self,
        target: ExecutionTarget,
        error: Exception,
        attempt: int,
    ) -> RecoveryDecision: ...


class DefaultIntelligenceFabric:
    """Foundational Intelligence Fabric orchestrator enforcing plane boundaries."""

    def __init__(self, provider_id: str = "default_fabric") -> None:
        self.provider_id = provider_id

    def resolve_target(self, target_id: str) -> ExecutionTarget:
        """Resolve a registered target into an explicit execution target."""
        return ExecutionTarget(target_id=target_id, action_name=target_id)

    def validate_execution(self, target: ExecutionTarget) -> ValidationResult:
        """Validate an execution target before routing."""
        return self.validate_target(target)

    def evaluate_recovery(
        self,
        target: ExecutionTarget,
        error: Exception,
        attempt: int,
    ) -> RecoveryDecision:
        """Evaluate bounded recovery for a failed execution target."""
        return self.handle_failure(target, error, attempt)

    def validate_target(self, target: ExecutionTarget) -> ValidationResult:
        """Explicitly validate execution target before routing."""
        if not isinstance(target.target_id, str) or not target.target_id:
            return ValidationResult(
                is_valid=False,
                reason="Target ID must be a non-empty string.",
            )
        if not isinstance(target.action_name, str) or not target.action_name:
            return ValidationResult(
                is_valid=False,
                reason="action_name must be a non-empty string.",
            )
        return ValidationResult(is_valid=True, reason="Target configuration is valid.")

    def handle_failure(
        self,
        target: ExecutionTarget,
        error: Exception,
        attempt: int,
    ) -> RecoveryDecision:
        """Determine an explicit recovery action to prevent silent failures."""
        if attempt < 3:
            return RecoveryDecision(
                action="retry",
                reason=f"Failure encountered ({error}); retrying attempt {attempt + 1}.",
                retry_count=attempt,
            )
        return RecoveryDecision(
            action="escalate",
            reason=f"Exceeded maximum retries ({attempt}) for target {target.target_id}. Error: {error}",
            retry_count=attempt,
        )

    def create_telemetry_event(
        self,
        event_type: str,
        details: dict[str, Any],
    ) -> StructuredEvent:
        """Emit a structured event for Observability plane consumption."""
        return StructuredEvent(
            event_id=f"evt_{datetime.now(UTC).timestamp()}",
            event_type=event_type,
            plane="IntelligenceFabric",
            details=details,
        )
