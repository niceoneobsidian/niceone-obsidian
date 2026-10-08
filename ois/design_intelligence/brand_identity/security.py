"""Security and trust boundary."""

from typing import Any


class DesignSecurityBoundary:
    SENSITIVE_KEYS = {"credentials", "api_key", "password", "secret", "private_key"}

    def classify_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = tuple(k for k in payload if k.lower() in self.SENSITIVE_KEYS)
        return {"classification": "restricted" if s else "standard", "sensitive_keys": s}

    def detect_sensitive_context(self, payload: dict[str, Any]) -> tuple[str, ...]:
        return tuple(k for k in payload if k.lower() in self.SENSITIVE_KEYS)

    def validate_access(self, classification: str, authorized: bool) -> bool:
        return authorized if classification == "restricted" else True

    def classify_output(self, output: dict[str, Any]) -> str:
        return "design_artifact"

    def audit_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "keys": sorted(payload),
            "redacted_sensitive": sorted(self.detect_sensitive_context(payload)),
        }
