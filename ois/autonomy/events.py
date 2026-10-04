"""Tenant-scoped event routing for autonomous operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

Handler = Callable[["EventEnvelope"], object]


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    tenant_id: str
    workspace_id: str
    event_type: str
    aggregate_id: str
    payload: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_id: str | None = None
    correlation_id: str | None = None

    @classmethod
    def from_outbox(cls, event: object) -> "EventEnvelope":
        return cls(
            event_id=str(getattr(event, "event_id")),
            tenant_id=str(getattr(event, "tenant_id")),
            workspace_id=str(getattr(event, "workspace_id")),
            event_type=str(getattr(event, "event_type")),
            aggregate_id=str(getattr(event, "aggregate_id")),
            payload=dict(getattr(event, "payload", {}) or {}),
            created_at=getattr(event, "created_at", datetime.now(UTC)),
        )


@dataclass(frozen=True)
class EventRoute:
    route_id: str
    event_type: str
    handler: Handler
    source_id: str | None = None


class EventRouter:
    def register(self, route: EventRoute) -> None: ...
    def route(self, event: EventEnvelope) -> tuple[object, ...]: ...


class InMemoryEventRouter(EventRouter):
    """Deterministic fan-out router. Tenant scope is carried by every event."""

    def __init__(self) -> None:
        self._routes: dict[str, EventRoute] = {}
        self._lock = RLock()

    def register(self, route: EventRoute) -> None:
        if not route.route_id or not route.event_type:
            raise ValueError("route_id and event_type are required")
        with self._lock:
            if route.route_id in self._routes:
                raise ValueError(f"event route already registered: {route.route_id}")
            self._routes[route.route_id] = route

    def route(self, event: EventEnvelope) -> tuple[object, ...]:
        with self._lock:
            routes = tuple(
                self._routes.values()
            )
        results: list[object] = []
        for route in routes:
            if route.event_type != event.event_type:
                continue
            if route.source_id is not None and route.source_id != event.source_id:
                continue
            results.append(route.handler(event))
        return tuple(results)


def new_event_id() -> str:
    return str(uuid4())
