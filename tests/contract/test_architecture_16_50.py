"""Contract coverage for architecture structures 16-50."""
from dataclasses import FrozenInstanceError
import pytest
from ois.architecture.base import Contract
from ois.architecture.execution_context import ExecutionContext
from ois.architecture.execution_lifecycle import ExecutionLifecycle, ExecutionState
from ois.architecture.execution_queue import ExecutionQueueItem
from ois.architecture.concurrency import ConcurrencyPolicy
from ois.architecture.idempotency import IdempotencyKey
from ois.architecture.failure_classification import FailureClassification
from ois.architecture.retry_policy import RetryPolicy
from ois.architecture.fallback import FallbackPlan
from ois.architecture.checkpoint import Checkpoint
from ois.architecture.escalation import EscalationRequest
from ois.architecture.agent_identity import AgentIdentity
from ois.architecture.agent_state import AgentStateRecord
from ois.architecture.agent_delegation import DelegationRequest
from ois.architecture.agent_communication import AgentMessage
from ois.architecture.agent_evaluation import AgentEvaluation
from ois.architecture.model_adapter import ModelAdapterSpec
from ois.architecture.model_policy import ModelPolicy
from ois.architecture.model_budget import ModelBudget
from ois.architecture.tool_contract import ToolContract
from ois.architecture.tool_sandbox import ToolSandboxPolicy
from ois.architecture.workflow_state import WorkflowState
from ois.architecture.workflow_dependencies import WorkflowDependency
from ois.architecture.knowledge import KnowledgeRecord
from ois.architecture.retrieval import RetrievalRequest
from ois.architecture.provenance import ProvenanceRecord
from ois.architecture.memory_policy import MemoryPolicy
from ois.architecture.memory_retrieval import MemoryQuery
from ois.architecture.supervisor_decisions import SupervisorDecision
from ois.architecture.governance import GovernanceDecision
from ois.architecture.audit import AuditRecord
from ois.architecture.events import OISEvent
from ois.architecture.traces import TraceContext
from ois.architecture.metrics import MetricSample
from ois.architecture.evaluation_experiments import Experiment
from ois.architecture.optimization_evolution import EvolutionCandidate

CONTRACTS = [ExecutionContext, ExecutionLifecycle, ExecutionQueueItem, ConcurrencyPolicy, IdempotencyKey, FailureClassification, RetryPolicy, FallbackPlan, Checkpoint, EscalationRequest, AgentIdentity, AgentStateRecord, DelegationRequest, AgentMessage, AgentEvaluation, ModelAdapterSpec, ModelPolicy, ModelBudget, ToolContract, ToolSandboxPolicy, WorkflowState, WorkflowDependency, KnowledgeRecord, RetrievalRequest, ProvenanceRecord, MemoryPolicy, MemoryQuery, SupervisorDecision, GovernanceDecision, AuditRecord, OISEvent, TraceContext, MetricSample, Experiment, EvolutionCandidate]

@pytest.mark.parametrize("contract_type", CONTRACTS)
def test_structures_are_immutable_versioned_contracts(contract_type: type[Contract]) -> None:
    item = contract_type(id=contract_type.__name__.lower(), version="1.0.0")
    assert item.id
    assert item.version == "1.0.0"
    with pytest.raises(FrozenInstanceError):
        item.version = "2.0.0"  # type: ignore[misc]


def test_execution_lifecycle_has_explicit_terminal_success_state() -> None:
    assert ExecutionState.VALIDATED.value == "validated"
