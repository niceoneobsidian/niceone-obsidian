from __future__ import annotations

from uuid import uuid4

from .checkpoint import CheckpointStore
from .contracts import InvocationRequest, InvocationResult
from .evidence import EvidenceLedger
from .policy import DefaultPolicyEngine, PolicyEngine
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
    """
    Foundational OIS Kernel execution runtime.

    Important boundary:
    Runtime executes ONE capability invocation.
    Plan completion is owned by the orchestrator.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        checkpoint_store: CheckpointStore,
        evidence: EvidenceLedger,
        *,
        validator: ContractValidator | None = None,
        policy: PolicyEngine | None = None,
        recovery: RecoveryPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.checkpoint_store = checkpoint_store
        self.evidence = evidence
        self.validator = validator or ContractValidator()
        self.policy = policy or DefaultPolicyEngine()
        self.recovery = recovery or RecoveryPolicy()

    def execute(
        self,
        context: ExecutionContext,
        capability_id: str,
        version: str,
        input_data: dict,
    ) -> InvocationResult:

        if context.status in {
            ExecutionStatus.STOPPED,
        }:
            raise ExecutionAlreadyCompleted(
                f"Execution cannot continue from "
                f"{context.status.value}."
            )

        execution_id = context.identity.execution_id

        self.evidence.record(
            execution_id,
            "execution.received",
            {
                "capability_id": capability_id,
                "version": version,
            },
        )

        context.set_status(
            ExecutionStatus.NORMALIZED
        )

        entry = self.registry.get(
            capability_id,
            version,
        )

        context.set_status(
            ExecutionStatus.PLAN_VALIDATED
        )

        request = InvocationRequest(
            invocation_id=str(uuid4()),
            capability_id=capability_id,
            input=input_data,
            execution=context,
            timeout_seconds=entry.contract.timeout_seconds,
        )

        # -------------------------
        # INPUT VALIDATION
        # -------------------------

        self.validator.validate_input(
            request,
            entry.contract,
        )

        self.evidence.record(
            execution_id,
            "execution.input_validated",
            {
                "capability_id": capability_id,
                "invocation_id": request.invocation_id,
            },
        )

        # -------------------------
        # AUTHORIZATION
        # -------------------------

        self.policy.authorize(
            request,
            entry.contract,
        )

        context.set_status(
            ExecutionStatus.AUTHORIZED
        )

        self.evidence.record(
            execution_id,
            "execution.authorized",
            {
                "capability_id": capability_id,
                "invocation_id": request.invocation_id,
            },
        )

        # -------------------------
        # EXECUTION
        # -------------------------

        context.set_status(
            ExecutionStatus.EXECUTING
        )

        self.evidence.record(
            execution_id,
            "capability.started",
            {
                "capability_id": capability_id,
                "invocation_id": request.invocation_id,
            },
        )

        try:
            result = entry.capability.invoke(
                request
            )

        except Exception as exc:
            return self._handle_failure(
                context,
                capability_id,
                exc,
            )

        # -------------------------
        # OBSERVATION
        # -------------------------

        context.set_status(
            ExecutionStatus.OBSERVING
        )

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

        # -------------------------
        # OUTPUT VALIDATION
        # -------------------------

        context.set_status(
            ExecutionStatus.VALIDATING
        )

        if result.status == InvocationStatus.SUCCEEDED:
            self.validator.validate_output(
                result,
                entry.contract,
            )

        context.validation_results.append(
            {
                "invocation_id": result.invocation_id,
                "valid": (
                    result.status
                    == InvocationStatus.SUCCEEDED
                ),
            }
        )

        # -------------------------
        # STATE UPDATE
        # -------------------------

        context.set_status(
            ExecutionStatus.UPDATING_STATE
        )

        if result.status == InvocationStatus.SUCCEEDED:
            context.working_memory[
                f"result:{result.invocation_id}"
            ] = result.output

        # -------------------------
        # CHECKPOINT
        # -------------------------

        context.set_status(
            ExecutionStatus.CHECKPOINTING
        )

        self.checkpoint_store.save(
            context
        )

        self.evidence.record(
            execution_id,
            "execution.checkpointed",
            {
                "capability_id": capability_id,
                "invocation_id": result.invocation_id,
            },
        )

        # -------------------------
        # RETURN TO ORCHESTRATOR
        # -------------------------

        # CRITICAL:
        # Do NOT mark the entire execution COMPLETED here.
        #
        # The orchestrator owns plan-level completion.

        context.set_status(
            ExecutionStatus.ROUTED
        )

        return result

    def complete(
        self,
        context: ExecutionContext,
    ) -> None:
        """
        Mark the entire execution complete.

        Called only after the plan/orchestrator has finished.
        """

        context.set_status(
            ExecutionStatus.COMPLETED
        )

        self.checkpoint_store.save(
            context
        )

        self.evidence.record(
            context.identity.execution_id,
            "execution.completed",
        )

    def _handle_failure(
        self,
        context: ExecutionContext,
        capability_id: str,
        error: Exception,
    ) -> InvocationResult:

        execution_id = context.identity.execution_id

        failure_class = FailureClass.TOOL

        decision = self.recovery.apply(
            context,
            failure_class,
        )

        self.evidence.record(
            execution_id,
            "execution.failure",
            {
                "capability_id": capability_id,
                "error": str(error),
                "failure_class": (
                    failure_class.value
                ),
                "recovery_action": (
                    decision.action
                ),
            },
        )

        self.checkpoint_store.save(
            context
        )

        return InvocationResult(
            invocation_id=str(uuid4()),
            capability_id=capability_id,
            status=InvocationStatus.FAILED,
            error={
                "type": type(error).__name__,
                "message": str(error),
                "failure_class": (
                    failure_class.value
                ),
                "recovery_action": (
                    decision.action
                ),
            },
        )
