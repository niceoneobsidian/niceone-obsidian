import pytest

from ois.runtime.agent_runtime import AgentRuntime, AgentWorkspace, InMemoryAgentMemory
from ois.runtime.llm_gateway import ModelOutput, ModelOutputError


class FakeGateway:
    def __init__(self, response: object | None = None) -> None:
        self.calls: list[dict] = []
        self.response = response if response is not None else ModelOutput("agent response")

    def invoke(
        self,
        *,
        model: str,
        messages: list[dict],
        timeout_seconds: float,
        metadata: dict | None = None,
    ) -> object:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "timeout_seconds": timeout_seconds,
                "metadata": metadata,
            }
        )
        return self.response


def test_agent_session_uses_workspace_memory_and_gateway() -> None:
    gateway = FakeGateway()
    memory = InMemoryAgentMemory()
    runtime = AgentRuntime(gateway, memory)
    runtime.register_workspace(AgentWorkspace(agent_id="agent-1", skills=("research",)))

    session = runtime.create_session("agent-1")
    result = runtime.run(session.session_id, "hello", model="test-model")

    assert result.status == "completed"
    assert result.output == "agent response"
    assert gateway.calls[0]["metadata"]["agent_id"] == "agent-1"
    assert gateway.calls[0]["timeout_seconds"] == 30.0
    assert memory.load("agent-1", session.session_id)[0]["content"] == "agent response"


def test_agent_runtime_rejects_command_shaped_model_output() -> None:
    memory = InMemoryAgentMemory()
    runtime = AgentRuntime(FakeGateway({"command": "rm -rf /tmp/not-a-command"}), memory)
    runtime.register_workspace(AgentWorkspace(agent_id="agent-1"))
    session = runtime.create_session("agent-1")

    with pytest.raises(ModelOutputError, match="invalid model output type"):
        runtime.run(session.session_id, "hello", model="test-model")

    assert memory.load("agent-1", session.session_id) == []


def test_agent_session_can_close() -> None:
    runtime = AgentRuntime(FakeGateway())
    runtime.register_workspace(AgentWorkspace(agent_id="agent-1"))
    session = runtime.create_session("agent-1")

    closed = runtime.close_session(session.session_id)

    assert closed.status == "closed"


def test_agent_workspace_rejects_invalid_timeout() -> None:
    for timeout in (0, -1, float("inf"), True, "1"):
        with pytest.raises(ValueError, match="timeout_seconds"):
            AgentWorkspace(agent_id="agent-1", timeout_seconds=timeout)  # type: ignore[arg-type]
