from ois.kernel import (
    AuthorizationDenied,
    CapabilityContract,
    CapabilityRegistry,
    InMemoryCheckpointStore,
    ContractValidator,
    DefaultPolicyEngine,
    EvidenceLedger,
    ExecutionContext,
    ExecutionIdentity,
    ExecutionRuntime,
    InvocationResult,
    InvocationStatus,
    RiskLevel,
    SideEffectLevel,
)


class RecordingCapability:
    def __init__(self, contract):
        self._contract = contract
        self.invoked = False
        self.request = None

    @property
    def contract(self):
        return self._contract

    def invoke(self, request):
        self.invoked = True
        self.request = request

        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=request.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"executed": True},
        )


def make_context(tenant_id="tenant-test"):
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id=tenant_id,
        ),
        objective="Runtime authorization integration test",
    )


def make_runtime(capability, policy):
    registry = CapabilityRegistry()
    registry.register(capability)

    return ExecutionRuntime(
        registry=registry,
        checkpoint_store=InMemoryCheckpointStore(),
        evidence=EvidenceLedger(),
        validator=ContractValidator(),
        policy=policy,
    )


def test_runtime_denied_authorization_blocks_capability_execution():
    capability = RecordingCapability(
        CapabilityContract(
            capability_id="test.runtime.policy",
            version="1.0.0",
            description="Runtime policy denial test",
            permissions=("restricted.action",),
        )
    )

    runtime = make_runtime(
        capability,
        DefaultPolicyEngine(
            allowed_permissions=(),
        ),
    )

    context = make_context()

    try:
        runtime.execute(
            context=context,
            capability_id="test.runtime.policy",
            version="1.0.0",
            input_data={},
        )
        raise AssertionError(
            "Runtime should reject unauthorized execution"
        )
    except AuthorizationDenied:
        pass

    assert capability.invoked is False
    assert context.status != context.status.EXECUTING


def test_runtime_authorized_execution_reaches_capability():
    capability = RecordingCapability(
        CapabilityContract(
            capability_id="test.runtime.policy",
            version="1.0.0",
            description="Runtime authorization success test",
        )
    )

    runtime = make_runtime(
        capability,
        DefaultPolicyEngine(),
    )

    context = make_context()

    result = runtime.execute(
        context=context,
        capability_id="test.runtime.policy",
        version="1.0.0",
        input_data={"value": "test"},
    )

    assert result.status == InvocationStatus.SUCCEEDED
    assert result.output == {"executed": True}

    assert capability.invoked is True
    assert capability.request is not None

    assert context.status == context.status.ROUTED


def test_runtime_denies_high_risk_when_policy_limit_is_medium():
    capability = RecordingCapability(
        CapabilityContract(
            capability_id="test.runtime.policy",
            version="1.0.0",
            description="Runtime risk boundary test",
            risk_level=RiskLevel.HIGH,
        )
    )

    runtime = make_runtime(
        capability,
        DefaultPolicyEngine(
            maximum_risk=RiskLevel.MEDIUM,
        ),
    )

    context = make_context()

    try:
        runtime.execute(
            context=context,
            capability_id="test.runtime.policy",
            version="1.0.0",
            input_data={},
        )
        raise AssertionError(
            "High-risk capability should be denied by medium-risk policy"
        )
    except AuthorizationDenied:
        pass

    assert capability.invoked is False


def test_runtime_denies_irreversible_action_by_default():
    capability = RecordingCapability(
        CapabilityContract(
            capability_id="test.runtime.policy",
            version="1.0.0",
            description="Runtime irreversible action test",
            side_effects=SideEffectLevel.IRREVERSIBLE,
        )
    )

    runtime = make_runtime(
        capability,
        DefaultPolicyEngine(
            allow_irreversible=False,
        ),
    )

    context = make_context()

    try:
        runtime.execute(
            context=context,
            capability_id="test.runtime.policy",
            version="1.0.0",
            input_data={},
        )
        raise AssertionError(
            "Irreversible capability should be denied"
        )
    except AuthorizationDenied:
        pass

    assert capability.invoked is False


def test_runtime_missing_tenant_identity_is_denied():
    capability = RecordingCapability(
        CapabilityContract(
            capability_id="test.runtime.policy",
            version="1.0.0",
            description="Runtime tenant identity test",
        )
    )

    runtime = make_runtime(
        capability,
        DefaultPolicyEngine(),
    )

    context = make_context(tenant_id="")

    try:
        runtime.execute(
            context=context,
            capability_id="test.runtime.policy",
            version="1.0.0",
            input_data={},
        )
        raise AssertionError(
            "Runtime should deny execution without tenant identity"
        )
    except AuthorizationDenied:
        pass

    assert capability.invoked is False
