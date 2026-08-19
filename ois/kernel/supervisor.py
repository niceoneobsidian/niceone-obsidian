
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .contracts import InvocationResult, InvocationStatus


@dataclass(frozen=True)
class SupervisorRequest:
    objective: str
    capability_id: str
    version: str
    input_data: Dict[str, Any]
    invocation_id: str


class Supervisor:
    """
    Deterministic governance/delegation layer above the execution runtime.

    The Supervisor does not execute capabilities itself. It validates the
    request and delegates execution to the existing runtime.
    """

    def __init__(self, runtime: Any):
        self.runtime = runtime

    def execute(
        self,
        *,
        objective: str,
        capability_id: str,
        version: str,
        input_data: Dict[str, Any],
        invocation_id: str,
        context: Any,
    ) -> InvocationResult:
        if not objective or not objective.strip():
            return InvocationResult(
                invocation_id=invocation_id,
                capability_id=capability_id,
                status=InvocationStatus.FAILED,
                output=None,
                error={
                    "type": "SupervisorValidationError",
                    "message": "objective is required",
                    "failure_class": "validation",
                    "recovery_action": "stop",
                },
            )

        if not capability_id or not capability_id.strip():
            return InvocationResult(
                invocation_id=invocation_id,
                capability_id=capability_id,
                status=InvocationStatus.FAILED,
                output=None,
                error={
                    "type": "SupervisorValidationError",
                    "message": "capability_id is required",
                    "failure_class": "validation",
                    "recovery_action": "stop",
                },
            )

        return self.runtime.execute(
            context=context,
            capability_id=capability_id,
            version=version,
            input_data=input_data,
            invocation_id=invocation_id,
        )
