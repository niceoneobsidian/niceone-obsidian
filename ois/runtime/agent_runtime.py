from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class AgentLLMGateway(Protocol):
    def invoke(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Any: ...


class AgentMemory(Protocol):
    def load(self, agent_id: str, session_id: str) -> list[dict[str, Any]]: ...

    def append(self, agent_id: str, session_id: str, item: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class AgentWorkspace:
    agent_id: str
    policy_ref: str | None = None
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    memory_ref: str | None = None


@dataclass
class AgentSession:
    session_id: str
    agent_id: str
    status: str = "active"
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AgentRunResult:
    session_id: str
    status: str
    output: Any
    model: str
    started_at: datetime
    completed_at: datetime


class InMemoryAgentMemory:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def load(self, agent_id: str, session_id: str) -> list[dict[str, Any]]:
        return list(self._items.get((agent_id, session_id), []))

    def append(self, agent_id: str, session_id: str, item: dict[str, Any]) -> None:
        self._items.setdefault((agent_id, session_id), []).append(dict(item))


class AgentRuntime:
    """Kernel-facing agent lifecycle using the OIS LLM gateway and memory boundaries."""

    def __init__(
        self,
        llm_gateway: AgentLLMGateway,
        memory: AgentMemory | None = None,
    ) -> None:
        self._llm_gateway = llm_gateway
        self._memory = memory or InMemoryAgentMemory()
        self._workspaces: dict[str, AgentWorkspace] = {}
        self._sessions: dict[str, AgentSession] = {}

    def register_workspace(self, workspace: AgentWorkspace) -> None:
        self._workspaces[workspace.agent_id] = workspace

    def create_session(self, agent_id: str) -> AgentSession:
        if agent_id not in self._workspaces:
            raise KeyError(f"Unknown agent workspace: {agent_id}")
        session = AgentSession(session_id=str(uuid4()), agent_id=agent_id)
        self._sessions[session.session_id] = session
        return session

    def run(
        self,
        session_id: str,
        prompt: str,
        *,
        model: str,
        context: list[dict[str, Any]] | None = None,
    ) -> AgentRunResult:
        session = self._sessions[session_id]
        workspace = self._workspaces[session.agent_id]
        started = datetime.now(UTC)
        history = self._memory.load(workspace.agent_id, session_id)
        messages = [*history, *(context or []), {"role": "user", "content": prompt}]
        session.messages.append(messages[-1])
        response = self._llm_gateway.invoke(
            model=model,
            messages=messages,
            metadata={"agent_id": workspace.agent_id, "session_id": session_id},
        )
        output = getattr(response, "output", response)
        assistant_message = {"role": "assistant", "content": output}
        session.messages.append(assistant_message)
        self._memory.append(workspace.agent_id, session_id, assistant_message)
        session.updated_at = datetime.now(UTC)
        completed = session.updated_at
        return AgentRunResult(session_id, "completed", output, model, started, completed)

    def close_session(self, session_id: str) -> AgentSession:
        session = self._sessions[session_id]
        session.status = "closed"
        session.updated_at = datetime.now(UTC)
        return session
