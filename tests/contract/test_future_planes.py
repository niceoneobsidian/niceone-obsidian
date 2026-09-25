"""Contract tests for the next OIS architectural planes."""

from ois.agents import AgentPlane
from ois.evolution import EvolutionCandidate, EvolutionPlane
from ois.execution import ExecutionPlane, ExecutionRequest
from ois.learning import LearningPlane
from ois.memory import MemoryPlane
from ois.models import ModelPlane, ModelRequest
from ois.observability import ObservabilityPlane
from ois.recovery import RecoveryPlane
from ois.supervisor import Supervisor
from ois.tools import ToolPlane, ToolRequest
from ois.validation import ValidationPlane
from ois.workflows import WorkflowPlane, WorkflowStep


def test_execution_validation_recovery_chain() -> None:
    result = ExecutionPlane().execute(
        lambda data: data["x"] + 1,
        ExecutionRequest("x", "1", {"x": 1}),  # type: ignore
    )
    assert ValidationPlane().validate(result).valid
    assert RecoveryPlane().decide(failure="failed", attempt=1, max_attempts=2).action == "retry"


def test_agent_model_tool_workflow_boundaries() -> None:
    assert AgentPlane().context("agent", "1").agent_id == "agent"
    model = type("Provider", (), {"invoke": lambda self, data: data})()
    assert ModelPlane().invoke(ModelRequest("model", "1", {"x": 1}), model).status == "success"
    tool = type("Tool", (), {"invoke": lambda self, data: data})()
    assert ToolPlane().invoke(ToolRequest("tool", "1", {"x": 1}), tool).status == "success"
    workflow = WorkflowPlane().define("wf", "1", (WorkflowStep("s1", "cap", "1"),))
    assert workflow.steps[0].step_id == "s1"


def test_supervisor_memory_observability_learning_evolution_boundaries() -> None:
    assert Supervisor().decide(status="success").action == "complete"
    memory = MemoryPlane()
    memory.append("k", "v1")
    memory.append("k", "v2")
    assert [entry.version for entry in memory.history("k")] == [1, 2]
    events = ObservabilityPlane()
    events.emit("execution.completed")
    assert len(events.events()) == 1
    candidate = LearningPlane().propose("c1", ("metric delta",), "change")
    assert candidate.evidence
    approved = EvolutionPlane().approve(EvolutionCandidate("e1", "1", ("eval",)))
    assert approved.approved
