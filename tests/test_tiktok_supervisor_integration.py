from ois.kernel.types import ExecutionStatus, InvocationStatus
from ois.workflows.tiktok_content_vertical_slice import execute_tiktok_vertical_slice


def test_supervisor_selects_agent_before_existing_kernel_execution_path() -> None:
    result = execute_tiktok_vertical_slice({"topic": "AI agents"})

    selection = result.context.metadata["supervisor_selection"]
    assert selection["capability_id"] == "tiktok.content.plan"
    assert selection["version"] == "1.0.0"
    assert selection["agent_type"].endswith("TikTokContentAgent")

    assert result.invocation.status == InvocationStatus.SUCCEEDED
    assert result.context.status == ExecutionStatus.COMPLETED

    event_types = [event.event_type for event in result.evidence]
    assert "execution.received" in event_types
    assert "execution.input_validated" in event_types
    assert "execution.authorized" in event_types
    assert "capability.started" in event_types

    received_index = event_types.index("execution.received")
    assert event_types.index("agent.selection.selected") < received_index
    assert "execution.completed" in event_types
