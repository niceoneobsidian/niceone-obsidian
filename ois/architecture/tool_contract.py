"""34. Tool Contract Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class ToolContract(Contract):
    input_schema: str = ""
    output_schema: str = ""
    side_effects: tuple[str, ...] = ()
