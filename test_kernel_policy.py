from ois.kernel import (
    AuthorizationDenied,
    CapabilityContract,
    DefaultPolicyEngine,
    ExecutionContext,
    ExecutionIdentity,
    InvocationRequest,
    RiskLevel,
    SideEffectLevel,
)


def make_request(tenant_id="tenant-test"):
    return InvocationRequest(
        invocation_id="policy-test-001",
        capability_id="test.policy",
        input={},
        execution=ExecutionContext(
            identity=ExecutionIdentity(
                tenant_id=tenant_id,
            ),
            objective="Policy verification test",
        ),
    )


def test_low_risk_capability_is_authorized():
    engine = DefaultPolicyEngine()

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Low-risk policy test",
    )

    request = make_request()

    assert engine.authorize(request, contract) is True


def test_missing_tenant_is_denied():
    engine = DefaultPolicyEngine()

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Tenant policy test",
    )

    decision = engine.evaluate(
        make_request(tenant_id=""),
        contract,
    )

    assert decision.allowed is False
    assert "tenant identity" in " ".join(decision.reasons).lower()


def test_excessive_risk_is_denied():
    engine = DefaultPolicyEngine(
        maximum_risk=RiskLevel.MEDIUM,
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="High-risk policy test",
        risk_level=RiskLevel.HIGH,
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is False
    assert any("risk" in reason.lower() for reason in decision.reasons)


def test_missing_permission_is_denied():
    engine = DefaultPolicyEngine(
        allowed_permissions=(),
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Permission policy test",
        permissions=("database.write",),
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is False
    assert any("missing permissions" in reason.lower() for reason in decision.reasons)


def test_irreversible_side_effect_is_denied_by_default():
    engine = DefaultPolicyEngine(
        allow_irreversible=False,
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Irreversible policy test",
        side_effects=SideEffectLevel.IRREVERSIBLE,
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is False
    assert any("irreversible" in reason.lower() for reason in decision.reasons)


def test_high_risk_requires_approval():
    engine = DefaultPolicyEngine(
        maximum_risk=RiskLevel.HIGH,
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Approval policy test",
        risk_level=RiskLevel.HIGH,
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is True
    assert decision.requires_approval is True


def test_critical_risk_requires_approval():
    engine = DefaultPolicyEngine(
        maximum_risk=RiskLevel.CRITICAL,
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Critical approval test",
        risk_level=RiskLevel.CRITICAL,
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is True
    assert decision.requires_approval is True


def test_irreversible_action_requires_approval():
    engine = DefaultPolicyEngine(
        allow_irreversible=True,
    )

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Irreversible approval test",
        side_effects=SideEffectLevel.IRREVERSIBLE,
    )

    decision = engine.evaluate(make_request(), contract)

    assert decision.allowed is True
    assert decision.requires_approval is True


def test_authorize_raises_when_policy_denies():
    engine = DefaultPolicyEngine()

    contract = CapabilityContract(
        capability_id="test.policy",
        version="1.0.0",
        description="Authorization denial test",
        permissions=("restricted.action",),
    )

    request = make_request()

    try:
        engine.authorize(request, contract)
        raise AssertionError("authorize() should raise AuthorizationDenied")
    except AuthorizationDenied:
        pass
