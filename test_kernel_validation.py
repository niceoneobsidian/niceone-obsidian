import pytest

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


@pytest.fixture
def contract():
    return CapabilityContract(
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


@pytest.fixture
def validator():
    return ContractValidator()


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


def test_valid_input_passes(validator, contract):
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


def test_missing_required_field_fails(validator, contract):
    with pytest.raises(InputValidationError):
        validator.validate_input(
            make_request(
                {
                    "message": "hello",
                }
            ),
            contract,
        )


def test_wrong_input_type_fails(validator, contract):
    with pytest.raises(InputValidationError):
        validator.validate_input(
            make_request(
                {
                    "message": "hello",
                    "count": "3",
                }
            ),
            contract,
        )


def test_invalid_enum_fails(validator, contract):
    with pytest.raises(InputValidationError):
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


def test_valid_output_passes(validator, contract):
    result = InvocationResult(
        invocation_id="validation-test-1",
        capability_id="test.validation",
        status=InvocationStatus.SUCCEEDED,
        output={
            "result": "success",
        },
    )

    validator.validate_output(result, contract)


def test_invalid_output_fails(validator, contract):
    result = InvocationResult(
        invocation_id="validation-test-1",
        capability_id="test.validation",
        status=InvocationStatus.SUCCEEDED,
        output={
            "result": 123,
        },
    )

    with pytest.raises(OutputValidationError):
        validator.validate_output(result, contract)
