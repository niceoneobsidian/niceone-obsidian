"""Observability and evidence preparation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .contracts import DesignArtifacts


class DesignOperations:
    def metrics(self, result: dict[str, Any]) -> dict[str, float]:
        v = result.get("validation")
        return {
            "execution_count": 1.0,
            "validation_passed": 1.0 if getattr(v, "passed", False) else 0.0,
            "confidence": float(getattr(result.get("identity"), "confidence", 0.0)),
        }

    def serializable(self, value: Any) -> Any:
        if hasattr(value, "__dataclass_fields__"):
            return asdict(value)
        if isinstance(value, dict):
            return {k: self.serializable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.serializable(v) for v in value]
        return value

    def artifact_names(self, artifacts: DesignArtifacts) -> tuple[str, ...]:
        return tuple(asdict(artifacts))
