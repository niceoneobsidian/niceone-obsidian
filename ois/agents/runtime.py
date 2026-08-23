"""Governed agent runtime boundary."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class AgentContext:
    agent_id: str
    version: str
    permissions: frozenset[str] = frozenset()
    metadata: Mapping[str, object] = field(default_factory=dict)

class AgentPlane:
    def context(self, agent_id: str, version: str, permissions: frozenset[str] = frozenset()) -> AgentContext:
        return AgentContext(agent_id, version, permissions)
