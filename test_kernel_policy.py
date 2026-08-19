from ois.kernel import (
    CapabilityContract,
    ExecutionContext,
    ExecutionIdentity,
    InvocationRequest,
    RiskLevel,
    SideEffectLevel,
)
from ois.kernel.policy import (
    AuthorizationDenied,
    DefaultPolicyEngine,
)


def make_request(tenant_id="default"):
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id=tenant_id),
        objective="Policy test",
    )

    return InvocationRequest(
        invocation_id="policy-test-1",
        capability_id="test.policy",
        input={},
        execution=context,
    )


def make_contract(**kwargs):
    values = {
        "capability_id": "test.policy",
        "version": "1.0.0",
        "description": "Policy test capability",
    }
    values.update(kwargs)
    return CapabilityContract(**values)


engine = DefaultPolicyEngine()

# Normal low-risk capability is allowed.
assert engine.authorize(
    make_request(),
    make_contract(),
) is True

# Missing tenant identity is denied.
try:
    engine.authorize(
        make_request(tenant_id=""),
        make_contract(),
    )
    raise AssertionError("Missing tenant should be denied")
except AuthorizationDenied:
    pass

# Excessive risk is denied by the default MEDIUM limit.
try:
    engine.authorize(
        make_request(),
        make_contract(risk_level=RiskLevel.HIGH),
    )
    raise AssertionError("High-risk capability should be denied")
except AuthorizationDenied:
    pass

# Missing permissions are denied.
permission_engine = DefaultPolicyEngine(
    allowed_permissions=(),
)

try:
    permission_engine.authorize(
        make_request(),
        make_contract(permissions=("publish",)),
    )
    raise AssertionError("Missing permission should be denied")
except AuthorizationDenied:
    pass

# Irreversible side effects are denied by default.
try:
    engine.authorize(
        make_request(),
        make_contract(
            side_effects=SideEffectLevel.IRREVERSIBLE,
        ),
    )
    raise AssertionError(
        "Irreversible side effect should be denied"
    )
except AuthorizationDenied:
    pass

# High-risk capability requires approval when the policy
# explicitly permits that risk level.
approval_engine = DefaultPolicyEngine(
    maximum_risk=RiskLevel.HIGH,
)

decision = approval_engine.evaluate(
    make_request(),
    make_contract(risk_level=RiskLevel.HIGH),
)

assert decision.allowed is True
assert decision.requires_approval is True

print("KERNEL POLICY TEST: PASS")
