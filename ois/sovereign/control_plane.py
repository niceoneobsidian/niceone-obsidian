"""Sovereign control-plane facade for governed execution."""

from __future__ import annotations

from typing import Any, Callable

from .contracts import AuthorizationDecision, ExecutionBackend, ExecutionRequest, ExecutionResult, ExecutionState

PolicyEvaluator = Callable[[ExecutionRequest], AuthorizationDecision]
EvidenceSink = Callable[[dict[str, Any]], None]


def default_policy(request: ExecutionRequest) -> AuthorizationDecision:
    if not request.capability.strip():
        return AuthorizationDecision(False, "capability is required")
    return AuthorizationDecision(True, "accepted by sovereign adapter policy")


class SovereignControlPlane:
    """Keeps policy and authorization above replaceable runtime providers."""

    def __init__(self, backend: ExecutionBackend, *, policy: PolicyEvaluator = default_policy,
                 evidence_sink: EvidenceSink | None = None) -> None:
        self.backend = backend
        self.policy = policy
        self.evidence_sink = evidence_sink

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        decision = self.policy(request)
        self._emit({"event": "authorization", "execution_id": request.execution_id,
                    "capability": request.capability, "tenant_id": request.tenant_id,
                    "allowed": decision.allowed, "reason": decision.reason,
                    "policy_version": decision.policy_version, "backend": self.backend.name})
        if not decision.allowed:
            result = ExecutionResult(request.execution_id, ExecutionState.ESCALATED, error=decision.reason)
            self._emit({"event": "execution_rejected", "execution_id": request.execution_id})
            return result
        result = self.backend.execute(request)
        self._emit({"event": "execution_result", "execution_id": result.execution_id,
                    "state": result.state.value, "backend": self.backend.name})
        return result

    def _emit(self, event: dict[str, Any]) -> None:
        if self.evidence_sink is not None:
            self.evidence_sink(event)
