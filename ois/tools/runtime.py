"""Tool invocation boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ToolRequest:
    tool_id: str
    version: str
    input: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    status: str
    output: object = None


class ToolInvoker(Protocol):
    def invoke(self, input: Mapping[str, object]) -> object: ...


class ToolPlane:
    def invoke(self, request: ToolRequest, tool: ToolInvoker) -> ToolResult:
        return ToolResult("success", tool.invoke(request.input))
