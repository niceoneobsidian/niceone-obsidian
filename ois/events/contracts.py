"""Event-driven architecture contracts."""
from dataclasses import dataclass

@dataclass(frozen=True)
class EventEnvelope:
    event_type: str
    event_id: str
    correlation_id: str
    payload: object
