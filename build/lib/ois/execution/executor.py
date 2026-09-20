"""Minimal execution boundary with authorization before side effects."""

from __future__ import annotations

from collections.abc import Callable

from .spec import AuthorizationError, ExecutionRequest, ExecutionResult


class ExecutionPlane:
    """Execute only an explicitly supplied callable after authorization."""

    def execute(
        self, target: Callable[[object], object], request: ExecutionRequest
    ) -> ExecutionResult:
        try:
            request.assert_authorized()
        except AuthorizationError as exc:
            return ExecutionResult(status="denied", error=str(exc))
        try:
            return ExecutionResult(status="success", output=target(request.input))
        except Exception as exc:  # noqa: BLE001 - boundary converts failures to results
            return ExecutionResult(status="failed", error=str(exc))
