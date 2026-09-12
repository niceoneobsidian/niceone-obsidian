from __future__ import annotations

from uuid import uuid4

from .cancellation import CancellationToken, ExecutionCancellation
from .checkpoint import CheckpointStore
from .contracts import InvocationRequest, InvocationResult
from .evidence import EvidenceLedger, EvidenceStore
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore
from .policy import DefaultPolicyEngine, PolicyEngine
from .recovery import RecoveryPolicy
from .registry import CapabilityRegistry
from .state import ExecutionContext
from .types import ExecutionStatus, FailureClass, InvocationStatus
from .validation import ContractValidator, OutputValidationError


class ExecutionError(Exception):
    """Base runtime execution error."""


class ExecutionAlreadyCompleted(ExecutionError):
    """Raised when an execution is submitted after completion."""


class ExecutionRuntime:
    """Foundational OIS Kernel runtime for one capability invocation."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        checkpoint_store: CheckpointStore,
        evidence: EvidenceStore | None = None,
        *,
        validator: ContractValidator | None = None,
        policy: PolicyEngine | None = None,
        recovery: RecoveryPolicy | None = None,
        cancellation: CancellationToken | None = None,
        idempotency: IdempotencyStore | None = None,
    ) -> None:
        self.registry = registry
        self.checkpoint_store = checkpoint_store
        self.evidence = evidence or EvidenceLedger()
        self.validator = validator or ContractValidator()
        self.policy = policy or DefaultPolicyEngine()
        self.recovery = recovery or RecoveryPolicy()
        self.cancellation = cancellation or CancellationToken()
        self.idempotency = idempotency or InMemoryIdempotencyStore()

    def execute(
        self,
        context: ExecutionContext,
        capability_id: str,
        version: str,
        input_data: dict,
        *,
        invocation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> InvocationResult:
        if context.status in {ExecutionStatus.COMPLETED, ExecutionStatus.STOPPED}:
            raise ExecutionAlreadyCompleted(
                f"Execution cannot continue from {context.status.value}."
            )

        if invocation_id is not None and idempotency_key is not None and invocation_id != idempotency_key:
            raise ExecutionError("invocation_id and idempotency_key must match when both are supplied.")

        logical_invocation_id = idempotency_key or invocation_id or str(uuid4())
        cached = self.idempotency.get(logical_invocation_id)
        if cached is not None:
            self.evidence.record(
                context.identity.execution_id,
                "execution.idempotency_hit",
                {
                    "capability_id": capability_id,
                    "version": version,
                    "invocation_id": logical_invocation_id,
                    "idempotency_key": logical_invocation_id,
                    "effect_invocation_id": cached.invocation_id,
                },
            )
            return cached

        execution_id = context.identity.execution_id
        self.evidence.record(
            execution_id,
            "execution.received",
            {
                "capability_id": capability_id,
                "version": version,
                "invocation_id": logical_invocation_id,
                "idempotency_key": logical_invocation_id,
            },
        )
        context.set_status(ExecutionStatus.NORMALIZED)
        entry = self.registry.get(capability_id, version)
        context.set_status(ExecutionStatus.PLAN_VALIDATED)

        try:
            self.cancellation.raise_if_cancelled()
        except ExecutionCancellation as exc:
            return self._handle_cancellation(context, capability_id, exc, logical_invocation_id)

        request = InvocationRequest(
            invocation_id=logical_invocation_id,
            capability_id=capability_id,
            input=input_data,
            execution=context,
            timeout_seconds=entry.contract.timeout_seconds,
            cancellation=self.cancellation,
        )
        self.validator.validate_input(request, entry.contract)
        self.evidence.record(
            execution_id,
            "execution.input_validated",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )
        self.policy.authorize(request, entry.contract)
        context.set_status(ExecutionStatus.AUTHORIZED)
        self.evidence.record(
            execution_id,
            "execution.authorized",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )

        context.set_status(ExecutionStatus.EXECUTING)
        context.current_node = capability_id
        self.checkpoint_store.save(context)
        self.evidence.record(
            execution_id,
            "capability.started",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )

        try:
            self.cancellation.raise_if_cancelled()
            result = entry.capability.invoke(request)
            self.cancellation.raise_if_cancelled()
        except ExecutionCancellation as exc:
            return self._handle_cancellation(context, capability_id, exc, logical_invocation_id)
        except Exception as exc:
            return self._handle_failure(context, capability_id, logical_invocation_id, exc)

        if (
            result.status == InvocationStatus.FAILED
            and isinstance(result.error, dict)
            and "failure_class" in result.error
        ):
            failure_value = result.error.get("failure_class")
            if isinstance(failure_value, str):
                try:
                    failure_class = FailureClass(failure_value)
                except ValueError:
                    failure_class = FailureClass.UNKNOWN
            else:
                failure_class = FailureClass.UNKNOWN
            decision = self.recovery.apply(context, failure_class)
            self.evidence.record(
                execution_id,
                "execution.recovery_decision",
                {
                    "capability_id": capability_id,
                    "invocation_id": logical_invocation_id,
                    "failure_class": failure_class.value,
                    "recovery_action": decision.action,
                },
            )
            self.checkpoint_store.save(context)
            result.error = {**result.error, "recovery_action": decision.action}

        if result.invocation_id != logical_invocation_id:
            raise ExecutionError(
                "Capability returned an invocation_id that does not match the requested "
                "invocation_id."
            )

        context.set_status(ExecutionStatus.OBSERVING)
        context.observations.append(
            {
                "invocation_id": result.invocation_id,
                "capability_id": result.capability_id,
                "status": result.status.value,
                "output": result.output,
            }
        )
        self.evidence.record(
            execution_id,
            "capability.completed",
            {
                "capability_id": capability_id,
                "invocation_id": result.invocation_id,
                "status": result.status.value,
            },
        )

        context.set_status(ExecutionStatus.VALIDATING)
        if result.status == InvocationStatus.SUCCEEDED:
            try:
                self.validator.validate_output(result, entry.contract)
            except OutputValidationError as exc:
                return self._handle_validation_failure(
                    context,
                    capability_id,
                    logical_invocation_id,
                    result,
                    exc,
                )

        context.validation_results.append(
            {
                "invocation_id": result.invocation_id,
                "valid": result.status == InvocationStatus.SUCCEEDED,
            }
        )
        self.evidence.record(
            execution_id,
            "execution.validation_passed",
            {"capability_id": capability_id, "invocation_id": result.invocation_id},
        )
        context.set_status(ExecutionStatus.UPDATING_STATE)
        if result.status == InvocationStatus.SUCCEEDED:
            context.working_memory[f"result:{result.invocation_id}"] = result.output

        self._cache_terminal_result(logical_invocation_id, result)
        self.evidence.record(
            execution_id,
            "execution.idempotency_recorded",
            {
                "capability_id": capability_id,
                "invocation_id": logical_invocation_id,
                "idempotency_key": logical_invocation_id,
                "status": result.status.value,
            },
        )
        context.set_status(ExecutionStatus.CHECKPOINTING)
        self.checkpoint_store.save(context)
        self.evidence.record(
            execution_id,
            "execution.checkpointed",
            {"capability_id": capability_id, "invocation_id": result.invocation_id},
        )
        context.set_status(ExecutionStatus.ROUTED)
        return result

    def complete(self, context: ExecutionContext) -> None:
        """Mark the entire execution complete only after successful validation."""
        invalid_results = [
            result
            for result in context.validation_results
            if result.get("valid") is False
        ]
        if invalid_results:
            self.evidence.record(
                context.identity.execution_id,
                "execution.completion_blocked",
                {"reason": "validation_failed", "invalid_results": len(invalid_results)},
            )
            self.checkpoint_store.save(context)
            raise ExecutionError("Execution cannot complete with failed validation.")

        if context.status in {ExecutionStatus.REPLANNING, ExecutionStatus.RECOVERING, ExecutionStatus.ESCALATED}:
            self.evidence.record(
                context.identity.execution_id,
                "execution.completion_blocked",
                {"reason": context.status.value},
            )
            self.checkpoint_store.save(context)
            raise ExecutionError(
                f"Execution cannot complete while in {context.status.value} recovery state."
            )

        context.set_status(ExecutionStatus.COMPLETED)
        self.checkpoint_store.save(context)
        self.evidence.record(context.identity.execution_id, "execution.completed")

    def _cache_terminal_result(self, invocation_id: str, result: InvocationResult) -> None:
        if result.status in {InvocationStatus.SUCCEEDED, InvocationStatus.CANCELLED}:
            self.idempotency.put(invocation_id, result)

    def _handle_validation_failure(
        self,
        context: ExecutionContext,
        capability_id: str,
        invocation_id: str,
        result: InvocationResult,
        error: OutputValidationError,
    ) -> InvocationResult:
        execution_id = context.identity.execution_id
        decision = self.recovery.apply(context, FailureClass.PLAN)
        context.validation_results.append(
            {
                "invocation_id": invocation_id,
                "valid": False,
                "errors": (str(error),),
            }
        )
        result.status = InvocationStatus.FAILED
        result.error = {
            "type": type(error).__name__,
            "message": str(error),
            "failure_class": FailureClass.PLAN.value,
            "recovery_action": decision.action,
        }
        self.evidence.record(
            execution_id,
            "execution.validation_failed",
            {
                "capability_id": capability_id,
                "invocation_id": invocation_id,
                "failure_class": FailureClass.PLAN.value,
                "recovery_action": decision.action,
                "error": str(error),
            },
        )
        self.evidence.record(
            execution_id,
            "execution.recovery_decision",
            {
                "capability_id": capability_id,
                "invocation_id": invocation_id,
                "failure_class": FailureClass.PLAN.value,
                "recovery_action": decision.action,
            },
        )
        self.checkpoint_store.save(context)
        return result

    def _handle_cancellation(
        self,
        context: ExecutionContext,
        capability_id: str,
        error: ExecutionCancellation,
        invocation_id: str,
    ) -> InvocationResult:
        execution_id = context.identity.execution_id
        context.set_status(ExecutionStatus.STOPPED)
        context.error = {
            "type": "ExecutionCancellation",
            "message": str(error),
            "failure_class": "cancellation",
            "recovery_action": "stop",
        }
        context.current_node = capability_id
        self.evidence.record(
            execution_id,
            "execution.cancelled",
            {"capability_id": capability_id, "invocation_id": invocation_id, "reason": str(error)},
        )
        self.checkpoint_store.save(context)
        return InvocationResult(
            invocation_id=invocation_id,
            capability_id=capability_id,
            status=InvocationStatus.CANCELLED,
            error={
                "type": "ExecutionCancellation",
                "message": str(error),
                "failure_class": "cancellation",
                "recovery_action": "stop",
            },
        )

    def _handle_failure(
        self,
        context: ExecutionContext,
        capability_id: str,
        invocation_id: str,
        error: Exception,
    ) -> InvocationResult:
        execution_id = context.identity.execution_id
        failure_class = FailureClass.TOOL
        decision = self.recovery.apply(context, failure_class)
        self.evidence.record(
            execution_id,
            "execution.failure",
            {
                "capability_id": capability_id,
                "error": str(error),
                "failure_class": failure_class.value,
                "recovery_action": decision.action,
                "invocation_id": invocation_id,
            },
        )
        self.checkpoint_store.save(context)
        return InvocationResult(
            invocation_id=invocation_id,
            capability_id=capability_id,
            status=InvocationStatus.FAILED,
            error={
                "type": type(error).__name__,
                "message": str(error),
                "failure_class": failure_class.value,
                "recovery_action": decision.action,
            },
        )
