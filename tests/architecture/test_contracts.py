from datetime import datetime, timedelta, timezone

import pytest

from ois.contracts import AuthorizationDecision, Decision, ExecutionRequest


def make_request(decision: Decision = Decision.ALLOW) -> ExecutionRequest:
    now = datetime.now(timezone.utc)
    auth = AuthorizationDecision(
        principal="test-principal",
        capability_id="test.capability",
        capability_version="1.0",
        policy_version="policy-1",
        decision=decision,
        reason="contract test",
        expires_at=now + timedelta(minutes=5),
    )
    return ExecutionRequest(
        principal="test-principal",
        capability_id="test.capability",
        capability_version="1.0",
        authorization=auth,
        deadline=now + timedelta(minutes=1),
        idempotency_key="idempotent-test",
    )


def test_side_effect_request_requires_allow_decision() -> None:
    make_request().assert_authorized()
    with pytest.raises(PermissionError):
        make_request(Decision.DENY).assert_authorized()


def test_mismatched_capability_fails_closed() -> None:
    request = make_request()
    request.capability_id = "other.capability"
    with pytest.raises(PermissionError):
        request.assert_authorized()
