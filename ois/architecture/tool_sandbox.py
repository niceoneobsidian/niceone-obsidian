"""35. Tool Sandbox Plane."""
from dataclasses import dataclass
from enum import Enum
from .base import Contract

class SideEffectClass(str, Enum):
    READ = "read"; WRITE = "write"; DESTRUCTIVE = "destructive"

@dataclass(frozen=True)
class ToolSandboxPolicy(Contract):
    allowed: tuple[SideEffectClass, ...] = (SideEffectClass.READ,)
