"""Tool invocation boundary."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

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
        invoke = getattr(tool, "invoke")
        return ToolResult("success", invoke(request.input))
