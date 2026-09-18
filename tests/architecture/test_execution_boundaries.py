from datetime import UTC, datetime, timedelta

from ois.execution.executor import ExecutionPlane
from ois.execution.spec import ExecutionRequest


def authorized_request(**kwargs):
    return ExecutionRequest(
        object_id="job-1",
        version="v1",
        input={"value": 1},
        capability="publish",
        idempotency_key="idem-1",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        authorization={"decision": "allow", "capability": "publish", "version": "v1"},
        **kwargs,
    )


def test_side_effect_requires_explicit_authorization():
    result = ExecutionPlane().execute(
        lambda data: data["value"],
        ExecutionRequest("job-1", "v1"),
    )
    assert result.status == "denied"


def test_authorized_side_effect_executes():
    result = ExecutionPlane().execute(
        lambda data: data["value"] + 1,
        authorized_request(),
    )
    assert result.status == "success"
    assert result.output == 2


def test_capability_mismatch_denies():
    request = authorized_request(capability="different")
    assert ExecutionPlane().execute(lambda _: "side effect", request).status == "denied"


def test_missing_capability_denies():
    request = authorized_request(capability=None)
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "capability identity required" in (result.error or "")


def test_missing_authorized_capability_denies():
    request = authorized_request(authorization={"decision": "allow", "version": "v1"})
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "authorized capability required" in (result.error or "")


def test_missing_authorized_version_denies():
    request = authorized_request(authorization={"decision": "allow", "capability": "publish"})
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "authorized version required" in (result.error or "")


def test_version_mismatch_denies():
    request = authorized_request(authorization={"decision": "allow", "capability": "publish", "version": "v2"})
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "version mismatch" in (result.error or "")


def test_wildcard_authorized_version_denies():
    request = authorized_request(authorization={"decision": "allow", "capability": "publish", "version": "*"})
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "version mismatch" in (result.error or "")


def test_missing_idempotency_key_denies():
    request = authorized_request(idempotency_key=None)
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "idempotency key required" in (result.error or "")


def test_expired_deadline_denies():
    request = authorized_request(deadline=datetime.now(UTC) - timedelta(seconds=1))
    result = ExecutionPlane().execute(lambda _: "side effect", request)
    assert result.status == "denied"
    assert "deadline expired" in (result.error or "")
