"""Deterministic validation boundary."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str = ""

class ValidationPlane:
    def validate(self, result: object) -> ValidationResult:
        return ValidationResult(result is not None, "" if result is not None else "result is None")
