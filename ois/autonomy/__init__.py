"""Phase C autonomous operations primitives."""

from .approvals import ApprovalDecision, ApprovalGate, ApprovalRequest, InMemoryApprovalStore
from .durable import (
    DurableRunStatus,
    DurableWorkflowRun,
    FencedPostgresWorkflowRunRepository,
    PostgresWorkflowRunRepository,
)
from .events import EventEnvelope, EventRoute, EventRouter, InMemoryEventRouter
from .loops import AutonomousLoop, LoopDecision, LoopState
from .operations import AutonomousOperations, OperationReceipt
from .policy import AutomationPolicy, PolicyEvaluation, PolicyRule
from .recovery import FailureRecovery, RecoveryAction, RecoveryRecord
from .recovery_store import RecoveryCandidate, WorkflowRecoverySweeper
from .workflows import SourceWorkflow, WorkflowRun, WorkflowStatus, WorkflowTrigger

__all__ = [
    "ApprovalDecision",
    "DurableRunStatus",
    "FencedPostgresWorkflowRunRepository",
    "DurableWorkflowRun",
    "PostgresWorkflowRunRepository",
    "ApprovalGate",
    "ApprovalRequest",
    "InMemoryApprovalStore",
    "EventEnvelope",
    "EventRouter",
    "EventRoute",
    "InMemoryEventRouter",
    "AutonomousLoop",
    "LoopDecision",
    "LoopState",
    "AutonomousOperations",
    "OperationReceipt",
    "AutomationPolicy",
    "PolicyEvaluation",
    "PolicyRule",
    "FailureRecovery",
    "RecoveryCandidate",
    "WorkflowRecoverySweeper",
    "RecoveryAction",
    "RecoveryRecord",
    "SourceWorkflow",
    "WorkflowRun",
    "WorkflowStatus",
    "WorkflowTrigger",
]
