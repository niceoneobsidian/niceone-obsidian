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
    assert event_types[:4] == [
        "execution.received",
        "execution.input_validated",
        "execution.authorized",
        "capability.started",
    ]
    assert "execution.completed" in event_types
