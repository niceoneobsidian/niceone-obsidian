"""47. Trace Plane."""
from dataclasses import dataclass
from .base import Contract

@dataclass(frozen=True)
class TraceContext(Contract):
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str | None = None
