from ois.kernel import (
    CapabilityContract,
    ExecutionContext,
    ExecutionIdentity,
    InvocationRequest,
    InvocationResult,
    InvocationStatus,
)
from ois.kernel.validation import (
    ContractValidator,
    InputValidationError,
    OutputValidationError,
)


contract = CapabilityContract(
    capability_id="test.validation",
    version="1.0.0",
    description="Validation test capability",
    input_schema={
        "type": "object",
        "required": ["message", "count"],
        "properties": {
            "message": {"type": "string"},
            "count": {"type": "integer"},
            "mode": {
                "type": "string",
                "enum": ["safe", "fast"],
            },
        },
    },
    output_schema={
        "type": "object",
        "required": ["result"],
        "properties": {
            "result": {"type": "string"},
        },
    },
)


def make_request(data):
    context = ExecutionContext(
        identity=ExecutionIdentity(tenant_id="default"),
        objective="Validation test",
    )

    return InvocationRequest(
        invocation_id="validation-test-1",
        capability_id="test.validation",
        input=data,
        execution=context,
    )


validator = ContractValidator()


# Valid input must pass.
validator.validate_input(
    make_request(
        {
            "message": "hello",
            "count": 3,
            "mode": "safe",
        }
    ),
    contract,
)


# Missing required field must fail.
try:
    validator.validate_input(
        make_request(
            {
                "message": "hello",
            }
        ),
        contract,
    )
    raise AssertionError("Missing required field should fail")
except InputValidationError:
    pass


# Wrong type must fail.
try:
    validator.validate_input(
        make_request(
            {
                "message": "hello",
                "count": "3",
            }
        ),
        contract,
    )
    raise AssertionError("Wrong type should fail")
except InputValidationError:
    pass


# Invalid enum must fail.
try:
    validator.validate_input(
        make_request(
            {
                "message": "hello",
                "count": 3,
                "mode": "unsafe",
            }
        ),
        contract,
    )
    raise AssertionError("Invalid enum should fail")
except InputValidationError:
    pass


# Valid output must pass.
valid_result = InvocationResult(
    invocation_id="validation-test-1",
    capability_id="test.validation",
    status=InvocationStatus.SUCCEEDED,
    output={
        "result": "success",
    },
)

validator.validate_output(
    valid_result,
    contract,
)


# Invalid output must fail.
invalid_result = InvocationResult(
    invocation_id="validation-test-1",
    capability_id="test.validation",
    status=InvocationStatus.SUCCEEDED,
    output={
        "result": 123,
    },
)

try:
    validator.validate_output(
        invalid_result,
        contract,
    )
    raise AssertionError("Invalid output should fail")
except OutputValidationError:
    pass


print("KERNEL VALIDATION TEST: PASS")
