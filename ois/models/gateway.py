"""Model gateway boundary."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class ModelRequest:
    model_id: str
    version: str
    input: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class ModelResult:
    status: str
    output: object = None

class ModelPlane:
    """Provider-neutral model invocation boundary."""
    def invoke(self, request: ModelRequest, provider: object) -> ModelResult:
        invoke = getattr(provider, "invoke")
        return ModelResult("success", invoke(request.input))
