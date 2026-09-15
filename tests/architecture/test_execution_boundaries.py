from datetime import UTC, datetime, timedelta

from ois.execution.executor import ExecutionPlane
from ois.execution.spec import ExecutionRequest


def authorized_request(**kwargs):
    return ExecutionRequest(
        object_id="job-1",
        version="v1",
        input={"value": 1},
        idempotency_key="idem-1",
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        authorization={"decision": "allow", "version": "v1"},
        **kwargs,
    )


def test_side_effect_requires_explicit_authorization():
    result = ExecutionPlane().execute(lambda data: data["value"], ExecutionRequest("job-1", "v1"))
    assert result.status == "denied"


def test_authorized_side_effect_executes():
    result = ExecutionPlane().execute(lambda data: data["value"] + 1, authorized_request())
    assert result.status == "success"
    assert result.output == 2


def test_capability_mismatch_denies():
    request = authorized_request(capability="publish")
    assert ExecutionPlane().execute(lambda _: "side effect", request).status == "denied"
