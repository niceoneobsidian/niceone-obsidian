from dataclasses import dataclass

from ois.runtime.agent_runtime import AgentRuntime, AgentWorkspace, InMemoryAgentMemory


@dataclass(frozen=True)
class Response:
    output: str


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def invoke(self, *, model: str, messages: list[dict], metadata: dict | None = None) -> Response:
        self.calls.append({"model": model, "messages": messages, "metadata": metadata})
        return Response(output="agent response")


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
    assert memory.load("agent-1", session.session_id)[0]["content"] == "agent response"


def test_agent_session_can_close() -> None:
    runtime = AgentRuntime(FakeGateway())
    runtime.register_workspace(AgentWorkspace(agent_id="agent-1"))
    session = runtime.create_session("agent-1")

    closed = runtime.close_session(session.session_id)

    assert closed.status == "closed"
