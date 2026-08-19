from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
)
from ois.kernel.recovery import RecoveryPolicy
from ois.kernel.types import (
    ExecutionStatus,
    FailureClass,
)


def make_context():
    return ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="Recovery test",
    )


policy = RecoveryPolicy(
    max_retries=2,
    max_recovery_attempts=2,
)

# TRANSIENT -> retry
context = make_context()
decision = policy.apply(context, FailureClass.TRANSIENT)

assert decision.action == "retry"
assert decision.retry_allowed is True
assert decision.terminal is False
assert context.retry_count == 1
assert context.status == ExecutionStatus.RECOVERING

# TRANSIENT retry limit -> escalate
context.retry_count = 2
decision = policy.apply(context, FailureClass.TRANSIENT)

assert decision.action == "escalate"
assert decision.terminal is True
assert context.status == ExecutionStatus.ESCALATED

# PARAMETER -> correct
context = make_context()
decision = policy.apply(context, FailureClass.PARAMETER)

assert decision.action == "correct"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.status == ExecutionStatus.RECEIVED

# TOOL -> fallback
context = make_context()
decision = policy.apply(context, FailureClass.TOOL)

assert decision.action == "fallback"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.status == ExecutionStatus.RECEIVED

# PLAN -> replan
context = make_context()
decision = policy.apply(context, FailureClass.PLAN)

assert decision.action == "replan"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.recovery_attempts == 1
assert context.status == ExecutionStatus.REPLANNING

# STATE -> recover
context = make_context()
decision = policy.apply(context, FailureClass.STATE)

assert decision.action == "recover"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.recovery_attempts == 1
assert context.status == ExecutionStatus.RECOVERING

# STATE recovery limit -> escalate
context.recovery_attempts = 2
decision = policy.apply(context, FailureClass.STATE)

assert decision.action == "escalate"
assert decision.terminal is True
assert context.status == ExecutionStatus.ESCALATED

# PERMISSION -> escalate
context = make_context()
decision = policy.apply(context, FailureClass.PERMISSION)

assert decision.action == "escalate"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.status == ExecutionStatus.ESCALATED

# SAFETY -> stop
context = make_context()
decision = policy.apply(context, FailureClass.SAFETY)

assert decision.action == "stop"
assert decision.retry_allowed is False
assert decision.terminal is True
assert context.status == ExecutionStatus.STOPPED

# UNKNOWN -> escalate
context = make_context()
decision = policy.apply(context, FailureClass.UNKNOWN)

assert decision.action == "escalate"
assert decision.retry_allowed is False
assert decision.terminal is False
assert context.status == ExecutionStatus.ESCALATED

print("KERNEL RECOVERY TEST: PASS")
