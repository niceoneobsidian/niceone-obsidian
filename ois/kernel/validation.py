from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
    def success(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def failure(cls, *errors: str) -> "ValidationResult":
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

    More sophisticated JSON Schema support can be introduced later without
    changing the Kernel validation boundary.
    """

    def validate_input(
        self,
        request: InvocationRequest,
        contract: CapabilityContract,
    ) -> None:
        result = self.validate_mapping(
            request.input,
            contract.input_schema,
        )

        if not result.valid:
            raise InputValidationError(
                "; ".join(result.errors)
            )

    def validate_output(
        self,
        result: InvocationResult,
        contract: CapabilityContract,
    ) -> None:
        if result.output is None:
            return

        schema = contract.output_schema

        if not schema:
            return

        validation = self.validate_mapping(
            result.output,
            schema,
        )

        if not validation.valid:
            raise OutputValidationError(
                "; ".join(validation.errors)
            )

    def validate_mapping(
        self,
        value: Any,
        schema: Mapping[str, Any],
    ) -> ValidationResult:
        errors: list[str] = []

        expected_type = schema.get("type")

        if expected_type == "object":
            if not isinstance(value, Mapping):
                return ValidationResult.failure(
                    "Expected object."
                )

            required = schema.get("required", [])

            for field in required:
                if field not in value:
                    errors.append(
                        f"Missing required field: {field}"
                    )

            properties = schema.get("properties", {})

            for name, property_schema in properties.items():
                if name not in value:
                    continue

                errors.extend(
                    self._validate_value(
                        value[name],
                        property_schema,
                        name,
                    )
                )

        else:
            errors.extend(
                self._validate_value(
                    value,
                    schema,
                    "value",
                )
            )

        return ValidationResult(
            valid=not errors,
            errors=tuple(errors),
        )

    def _validate_value(
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
            "number": lambda v: isinstance(v, (int, float))
            and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "object": lambda v: isinstance(v, Mapping),
            "array": lambda v: isinstance(v, (list, tuple)),
        }

        validator = type_validators.get(expected_type)

        if validator is not None and not validator(value):
            errors.append(
                f"{path}: expected {expected_type}."
            )
            return errors

        enum = schema.get("enum")

        if enum is not None and value not in enum:
            errors.append(
                f"{path}: value is not allowed."
            )

        return errors
