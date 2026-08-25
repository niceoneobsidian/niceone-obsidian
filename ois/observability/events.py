"""Structured append-only observability events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    name: str
    attributes: Mapping[str, object] = field(default_factory=dict)


class ObservabilityPlane:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def emit(self, name: str, attributes: Mapping[str, object] | None = None) -> Event:
        event = Event(name, dict(attributes or {}))
        self._events.append(event)
        return event

    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)
