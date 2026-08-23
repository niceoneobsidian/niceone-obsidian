"""21. Failure Classification Plane."""
from dataclasses import dataclass
from enum import Enum
from .base import Contract

class FailureClass(str, Enum):
    POLICY = "policy"; VALIDATION = "validation"; TIMEOUT = "timeout"; DEPENDENCY = "dependency"; TOOL = "tool"; MODEL = "model"; INFRASTRUCTURE = "infrastructure"; UNKNOWN = "unknown"

@dataclass(frozen=True)
class FailureClassification(Contract):
    category: FailureClass = FailureClass.UNKNOWN
