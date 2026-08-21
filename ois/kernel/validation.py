from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .contracts import CapabilityContract, InvocationRequest, InvocationResult


class ValidationError(Exception):
    """Base validation error."""


class InputValidationError(ValidationError):
    """Raised when invocation input violates a contract."""


class OutputValidationError(ValidationError):
    """Raised when invocation output violates a contract."""


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()

    @classmethod
    def success(cls) -> ValidationResult:
        return cls(valid=True)

    @classmethod
    def failure(cls, *errors: str) -> ValidationResult:
        return cls(valid=False, errors=tuple(errors))


class ContractValidator:
    """
    Deterministic validator for the foundational Kernel contracts.

    Supported schema vocabulary intentionally starts small:
    - object
    - required
    - properties
    - type
    - enum
    """

    def validate_input(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> None:
        errors = self._validate_schema(request.input, contract.input_schema, path="input")
        if errors:
            raise InputValidationError("; ".join(errors))

    def validate_output(
        self,
        result: InvocationResult,
        contract: CapabilityContract,
    ) -> None:
        errors = self._validate_schema(result.output, contract.output_schema, path="output")
        if errors:
            raise OutputValidationError("; ".join(errors))

    def _validate_schema(
        self,
        value: Any,
        schema: Mapping[str, Any],
        path: str,
    ) -> list[str]:
        errors: list[str] = []

        expected_type = schema.get("type")
        type_validators = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "object": lambda v: isinstance(v, Mapping),
            "array": lambda v: isinstance(v, (list, tuple)),
        }

        if isinstance(expected_type, str):
            validator = type_validators.get(expected_type)
            if validator is not None and not validator(value):
                errors.append(f"{path}: expected {expected_type}.")
                return errors

        enum = schema.get("enum")
        if isinstance(enum, (list, tuple)) and value not in enum:
            errors.append(f"{path}: value is not one of the allowed enum values.")

        required = schema.get("required")
        properties = schema.get("properties")
        if isinstance(required, (list, tuple)) and isinstance(value, Mapping):
            for field_name in required:
                if isinstance(field_name, str) and field_name not in value:
                    errors.append(f"{path}: missing required field '{field_name}'.")

        if isinstance(properties, Mapping) and isinstance(value, Mapping):
            for field_name, field_schema in properties.items():
                if field_name in value and isinstance(field_schema, Mapping):
                    errors.extend(
                        self._validate_schema(
                            value[field_name],
                            field_schema,
                            path=f"{path}.{field_name}",
                        )
                    )

        return errors
