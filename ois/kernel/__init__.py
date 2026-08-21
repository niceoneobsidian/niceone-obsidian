"""OIS Kernel public contracts and execution primitives."""

from .cancellation import CancellationToken, ExecutionCancellation

from .checkpoint import (
    CheckpointNotFound,
    CheckpointStore,
    InMemoryCheckpointStore,
    JsonFileCheckpointStore,
)

from .contracts import (
    AgentContract,
    Capability,
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
    PolicyEngine,
    ToolContract,
    Validator,
)

from .evidence import EvidenceEvent, EvidenceLedger

from .idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
    SQLiteIdempotencyStore,
)

from .planning import (
    CyclicPlanError,
    DuplicateTaskError,
    ExecutionPlan,
    PlanError,
    TaskNode,
    TaskStatus,
    UnknownDependencyError,
)

from .planner import PlanBuilder

from .orchestrator import (
    OrchestrationError,
    PlanExecutionError,
    PlanOrchestrator,
)

from .policy import (
    AuthorizationDenied,
    DefaultPolicyEngine,
    PolicyDecision,
)

from .runtime import ExecutionError, ExecutionRuntime
from .supervisor import Supervisor

from .recovery import (
    RecoveryDecision,
    RecoveryPolicy,
    RetryLimitExceeded,
)

from .registry import (
    AgentRegistry,
    CapabilityNotFoundError,
    CapabilityRegistry,
    DuplicateCapabilityError,
    ToolRegistry,
)

from .state import ExecutionContext, ExecutionIdentity

from .types import (
    ExecutionStatus,
    FailureClass,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)

from .validation import (
    ContractValidator,
    InputValidationError,
    OutputValidationError,
    ValidationError,
    ValidationResult,
)


__all__ = [
    # Contracts
    "AgentContract",
    "Capability",
    "CapabilityContract",
    "InvocationRequest",
    "InvocationResult",
    "PolicyEngine",
    "ToolContract",
    "Validator",

    # Cancellation
    "CancellationToken",
    "ExecutionCancellation",

    # Checkpoints
    "CheckpointNotFound",
    "CheckpointStore",
    "InMemoryCheckpointStore",
    "JsonFileCheckpointStore",

    # Evidence
    "EvidenceEvent",
    "EvidenceLedger",

    # Idempotency
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "SQLiteIdempotencyStore",

    # Planning
    "CyclicPlanError",
    "DuplicateTaskError",
    "ExecutionPlan",
    "PlanError",
    "TaskNode",
    "TaskStatus",
    "UnknownDependencyError",

    # Planner
    "PlanBuilder",

    # Orchestration
    "OrchestrationError",
    "PlanExecutionError",
    "PlanOrchestrator",

    # Policy
    "AuthorizationDenied",
    "DefaultPolicyEngine",
    "PolicyDecision",

    # Runtime
    "ExecutionError",
    "ExecutionRuntime",

    # Recovery
    "RecoveryDecision",
    "RecoveryPolicy",
    "RetryLimitExceeded",

    # Registry
    "AgentRegistry",
    "CapabilityNotFoundError",
    "CapabilityRegistry",
    "DuplicateCapabilityError",
    "ToolRegistry",

    # State
    "ExecutionContext",
    "ExecutionIdentity",

    # Types
    "ExecutionStatus",
    "FailureClass",
    "InvocationStatus",
    "RiskLevel",
    "SideEffectLevel",

    # Validation
    "ContractValidator",
    "InputValidationError",
    "OutputValidationError",
    "ValidationError",
    "ValidationResult",

    # Supervisor
    "Supervisor",
]