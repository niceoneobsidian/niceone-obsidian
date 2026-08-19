
from ois.kernel import (
    CapabilityRegistry,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InMemoryCheckpointStore,
    InvocationStatus,
    Supervisor,
)


class SupervisorCapability:
    capability_id = "test.supervisor"
    version = "1.0.0"
    permissions = []
    risk_level = "low"
    side_effects = False

    def execute(self, input_data):
        return {"supervised": input_data}


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(
            execution_id="supervisor-test-001",
            tenant_id="tenant-supervisor",
        )
    )


def make_supervisor():
    registry = CapabilityRegistry()
    registry.register(SupervisorCapability())

    runtime = ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
    )

    return Supervisor(runtime)


def test_supervisor_delegates_to_runtime():
    supervisor = make_supervisor()

    result = supervisor.execute(
        objective="Execute supervised capability",
        capability_id="test.supervisor",
        version="1.0.0",
        input_data={"value": 42},
        invocation_id="supervisor-invocation-001",
        context=make_context(),
    )

    assert result.status == InvocationStatus.SUCCEEDED


def test_supervisor_rejects_missing_objective():
    supervisor = make_supervisor()

    result = supervisor.execute(
        objective="",
        capability_id="test.supervisor",
        version="1.0.0",
        input_data={},
        invocation_id="supervisor-validation-001",
        context=make_context(),
    )

    assert result.status == InvocationStatus.FAILED
    assert result.error["failure_class"] == "validation"


def test_supervisor_rejects_missing_capability():
    supervisor = make_supervisor()

    result = supervisor.execute(
        objective="Execute something",
        capability_id="",
        version="1.0.0",
        input_data={},
        invocation_id="supervisor-validation-002",
        context=make_context(),
    )

    assert result.status == InvocationStatus.FAILED
    assert result.error["failure_class"] == "validation"
