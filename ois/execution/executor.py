"""Minimal execution boundary; resolution remains the router's concern."""
from __future__ import annotations
from collections.abc import Callable
from .spec import ExecutionRequest, ExecutionResult

class ExecutionPlane:
    """Execute only an explicitly supplied resolved callable."""
    def execute(self, target: Callable[..., object], request: ExecutionRequest) -> ExecutionResult:
        try:
            return ExecutionResult(status="success", output=target(request.input))
        except Exception as exc:
            return ExecutionResult(status="failed", error=str(exc))
