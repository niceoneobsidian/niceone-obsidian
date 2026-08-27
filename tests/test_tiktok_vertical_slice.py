from ois.kernel.types import ExecutionStatus, InvocationStatus
from ois.workflows.tiktok_content_vertical_slice import (
    VERTICAL_SLICE_VERSION,
    VERTICAL_SLICE_WORKFLOW_ID,
    execute_tiktok_vertical_slice,
)


def test_tiktok_vertical_slice_proves_kernel_path() -> None:
    result = execute_tiktok_vertical_slice(
        {
            "topic": "AI content strategy",
            "audience": "content creators",
            "objective": "education",
            "tone": "clear",
        }
    )

    assert result.invocation.status == InvocationStatus.SUCCEEDED
    assert result.plan.is_complete()
    assert result.plan.tasks["create_content_plan"].status.value == "succeeded"
    assert result.context.status == ExecutionStatus.COMPLETED
    assert result.context.identity.workflow_id == VERTICAL_SLICE_WORKFLOW_ID
    assert result.context.identity.workflow_version == VERTICAL_SLICE_VERSION
    assert result.context.metadata["supervised"] is True
    assert result.context.validation_results[-1]["valid"] is True
    assert result.context.working_memory

    event_types = [event.event_type for event in result.evidence]
    assert "agent.selection.selected" in event_types
    assert event_types.index("agent.selection.selected") < event_types.index("execution.received")
    assert event_types[:5] == [
        "agent.selection.selected",
        "execution.received",
        "execution.input_validated",
        "execution.authorized",
        "capability.started",
    ]
    assert "capability.completed" in event_types
    assert "execution.checkpointed" in event_types
    assert "execution.idempotency_recorded" in event_types
    assert "execution.completed" in event_types


def test_tiktok_vertical_slice_emits_provenance() -> None:
    result = execute_tiktok_vertical_slice({"topic": "AI agents"})

    provenance = result.invocation.metadata["execution_provenance"]
    assert provenance["capability_version"] == "1.0.0"
    assert len(provenance["input_sha256"]) == 64
