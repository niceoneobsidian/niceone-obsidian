from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic

from .contracts import Measurement, PlatformIdentity, utc_now


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    identity: PlatformIdentity
    attributes: dict[str, object] = field(default_factory=dict)
    recorded_at: object = field(default_factory=utc_now)


class MetricsStore:
    def __init__(self) -> None:
        self._measurements: list[Measurement] = []
        self._events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def measure(self, item: Measurement) -> None:
        self._measurements.append(item)

    def measurements(self) -> tuple[Measurement, ...]:
        return tuple(self._measurements)

    def events(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)


class ExecutionTimer:
    def __init__(self, metrics: MetricsStore, identity: PlatformIdentity, name: str) -> None:
        self.metrics, self.identity, self.name = metrics, identity, name
        self.started = 0.0

    def __enter__(self) -> ExecutionTimer:
        self.started = monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        self.metrics.measure(
            Measurement(
                self.name,
                (monotonic() - self.started) * 1000,
                "ms",
                dimensions={"tenant_id": self.identity.tenant_id},
            )
        )
