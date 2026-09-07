"""Tool invocation boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolRequest:
    tool_id: str
    version: str
    input: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    status: str
    output: object = None


class ToolPlane:
    def invoke(self, request: ToolRequest, tool: object) -> ToolResult:
        invoke = tool.invoke  # type: ignore
        return ToolResult("success", invoke(request.input))
