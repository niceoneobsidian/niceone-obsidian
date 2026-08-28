from __future__ import annotations

from uuid import uuid4

from .cancellation import CancellationToken, ExecutionCancellation
from .checkpoint import CheckpointStore
from .contracts import InvocationRequest, InvocationResult
from .evidence import EvidenceLedger
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore
from .policy import DefaultPolicyEngine, PolicyEngine
from .postgres import ExecutionLease, PostgreSQLExecutionCoordinator
from .recovery import RecoveryPolicy
from .registry import CapabilityRegistry
from .state import ExecutionContext
from .types import ExecutionStatus, FailureClass, InvocationStatus
from .validation import ContractValidator


class ExecutionError(Exception):
    """Base runtime execution error."""


class ExecutionAlreadyCompleted(ExecutionError):
    """Raised when an execution is submitted after completion."""


class ExecutionRuntime:
    """Foundational OIS Kernel execution runtime with optional lease fencing."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        checkpoint_store: CheckpointStore,
        evidence: EvidenceLedger,
        *,
        validator: ContractValidator | None = None,
        policy: PolicyEngine | None = None,
        recovery: RecoveryPolicy | None = None,
        cancellation: CancellationToken | None = None,
        idempotency: IdempotencyStore | None = None,
        coordinator: PostgreSQLExecutionCoordinator | None = None,
    ) -> None:
        self.registry = registry
        self.checkpoint_store = checkpoint_store
        self.evidence = evidence
        self.validator = validator or ContractValidator()
        self.policy = policy or DefaultPolicyEngine()
        self.recovery = recovery or RecoveryPolicy()
        self.cancellation = cancellation or CancellationToken()
        self.idempotency = idempotency or InMemoryIdempotencyStore()
        self.coordinator = coordinator

    def execute(
        self,
        context: ExecutionContext,
        capability_id: str,
        version: str,
        input_data: dict,
        *,
        invocation_id: str | None = None,
        lease: ExecutionLease | None = None,
    ) -> InvocationResult:
        self._assert_lease(lease)
        if context.status in {ExecutionStatus.COMPLETED, ExecutionStatus.STOPPED}:
            raise ExecutionAlreadyCompleted(
                f"Execution cannot continue from {context.status.value}."
            )

        execution_id = context.identity.execution_id
        logical_invocation_id = invocation_id or str(uuid4())
        self._assert_lease(lease)
        cached = self.idempotency.get(logical_invocation_id)
        if cached is not None:
            self.evidence.record(
                execution_id,
                "execution.idempotency_hit",
                {"capability_id": capability_id, "version": version, "invocation_id": logical_invocation_id},
            )
            return cached

        self.evidence.record(
            execution_id,
            "execution.received",
            {"capability_id": capability_id, "version": version, "invocation_id": logical_invocation_id},
        )
        context.set_status(ExecutionStatus.NORMALIZED)
        entry = self.registry.get(capability_id, version)
        context.set_status(ExecutionStatus.PLAN_VALIDATED)
        self._assert_lease(lease)

        try:
            self.cancellation.raise_if_cancelled()
        except ExecutionCancellation as exc:
            return self._handle_cancellation(context, capability_id, exc, logical_invocation_id, lease)

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
            execution_id, "execution.input_validated",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )
        self.policy.authorize(request, entry.contract)
        context.set_status(ExecutionStatus.AUTHORIZED)
        self.evidence.record(
            execution_id, "execution.authorized",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )

        self._assert_lease(lease)
        context.set_status(ExecutionStatus.EXECUTING)
        self.evidence.record(
            execution_id, "capability.started",
            {"capability_id": capability_id, "invocation_id": request.invocation_id},
        )

        try:
            self.cancellation.raise_if_cancelled()
            result = entry.capability.invoke(request)
            self.cancellation.raise_if_cancelled()
        except ExecutionCancellation as exc:
            return self._handle_cancellation(context, capability_id, exc, logical_invocation_id, lease)
        except Exception as exc:
            return self._handle_failure(context, capability_id, logical_invocation_id, exc, lease)

        self._assert_lease(lease)
        if result.invocation_id != logical_invocation_id:
            raise ExecutionError("Capability returned an invocation_id that does not match the requested invocation_id.")

        context.set_status(ExecutionStatus.OBSERVING)
        context.observations.append({
            "invocation_id": result.invocation_id,
            "capability_id": result.capability_id,
            "status": result.status.value,
            "output": result.output,
        })
        self.evidence.record(
            execution_id, "capability.completed",
            {"capability_id": capability_id, "invocation_id": result.invocation_id, "status": result.status.value},
        )
        context.set_status(ExecutionStatus.VALIDATING)
        if result.status == InvocationStatus.SUCCEEDED:
            self.validator.validate_output(result, entry.contract)
        context.validation_results.append({
            "invocation_id": result.invocation_id,
            "valid": result.status == InvocationStatus.SUCCEEDED,
        })
        context.set_status(ExecutionStatus.UPDATING_STATE)
        if result.status == InvocationStatus.SUCCEEDED:
            context.working_memory[f"result:{result.invocation_id}"] = result.output

        self._assert_lease(lease)
        context.set_status(ExecutionStatus.CHECKPOINTING)
        self.checkpoint_store.save(context)
        self.evidence.record(
            execution_id, "execution.checkpointed",
            {"capability_id": capability_id, "invocation_id": result.invocation_id},
        )
        if result.status == InvocationStatus.SUCCEEDED:
            self._assert_lease(lease)
            self.idempotency.put(logical_invocation_id, result)
            self.evidence.record(
                execution_id, "execution.idempotency_recorded",
                {"capability_id": capability_id, "invocation_id": logical_invocation_id, "status": result.status.value},
            )
        context.set_status(ExecutionStatus.ROUTED)
        return result

    def complete(self, context: ExecutionContext, *, lease: ExecutionLease | None = None) -> None:
        self._assert_lease(lease)
        context.set_status(ExecutionStatus.COMPLETED)
        self._assert_lease(lease)
        self.checkpoint_store.save(context)
        self.evidence.record(context.identity.execution_id, "execution.completed")

    def _assert_lease(self, lease: ExecutionLease | None) -> None:
        if lease is not None:
            if self.coordinator is None:
                raise ExecutionError("a lease was supplied without a coordinator")
            self.coordinator.assert_current(lease)

    def _handle_cancellation(self, context: ExecutionContext, capability_id: str,
                             error: ExecutionCancellation, invocation_id: str,
                             lease: ExecutionLease | None) -> InvocationResult:
        execution_id = context.identity.execution_id
        context.set_status(ExecutionStatus.STOPPED)
        context.error = {"type": "ExecutionCancellation", "message": str(error),
                         "failure_class": "cancellation", "recovery_action": "stop"}
        context.current_node = capability_id
        self.evidence.record(execution_id, "execution.cancelled",
                             {"capability_id": capability_id, "invocation_id": invocation_id, "reason": str(error)})
        self._assert_lease(lease)
        self.checkpoint_store.save(context)
        return InvocationResult(invocation_id=invocation_id, capability_id=capability_id,
                                 status=InvocationStatus.FAILED, error=context.error)

    def _handle_failure(self, context: ExecutionContext, capability_id: str,
                        invocation_id: str, error: Exception,
                        lease: ExecutionLease | None) -> InvocationResult:
        execution_id = context.identity.execution_id
        failure_class = FailureClass.TOOL
        decision = self.recovery.apply(context, failure_class)
        self.evidence.record(
            execution_id, "execution.failure",
            {"capability_id": capability_id, "error": str(error),
             "failure_class": failure_class.value, "recovery_action": decision.action,
             "invocation_id": invocation_id},
        )
        self._assert_lease(lease)
        self.checkpoint_store.save(context)
        return InvocationResult(
            invocation_id=invocation_id, capability_id=capability_id,
            status=InvocationStatus.FAILED,
            error={"type": type(error).__name__, "message": str(error),
                   "failure_class": failure_class.value, "recovery_action": decision.action},
        )
