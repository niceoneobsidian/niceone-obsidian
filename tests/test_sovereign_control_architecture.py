from __future__ import annotations

from ois.sovereign.contracts import (
    AuthorizationDecision,
    ExecutionRequest,
    ExecutionResult,
    ExecutionState,
)
from ois.sovereign.control_plane import SovereignControlPlane


class StubBackend:
    name = "stub"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(request.execution_id, ExecutionState.SUCCEEDED, output=request.input)


def test_control_plane_authorizes_before_execution() -> None:
    seen: list[dict[str, object]] = []

    def deny(request: ExecutionRequest) -> AuthorizationDecision:
        return AuthorizationDecision(False, "denied by test policy")

    result = SovereignControlPlane(StubBackend(), policy=deny, evidence_sink=seen.append).execute(
        ExecutionRequest(capability="email.send", input={"to": "example"})
    )

    assert result.state is ExecutionState.ESCALATED
    assert result.error == "denied by test policy"
    assert any(event["event"] == "execution_rejected" for event in seen)


def test_control_plane_routes_authorized_request() -> None:
    result = SovereignControlPlane(StubBackend()).execute(
        ExecutionRequest(capability="knowledge.search", input={"query": "OIS"})
    )

    assert result.state is ExecutionState.SUCCEEDED
    assert result.output == {"query": "OIS"}
