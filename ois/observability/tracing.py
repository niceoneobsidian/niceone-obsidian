"""OpenTelemetry instrumentation boundary for OIS executions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace


class OISTracer:
    """Emit bounded execution spans without coupling OIS to an exporter."""

    def __init__(self, name: str = "ois") -> None:
        self._tracer = trace.get_tracer(name)

    @contextmanager
    def execution_span(
        self,
        *,
        execution_id: str,
        capability_id: str,
        tenant_id: str,
    ) -> Iterator[Any]:
        with self._tracer.start_as_current_span("ois.execution") as span:
            span.set_attribute("ois.execution_id", execution_id)
            span.set_attribute("ois.capability_id", capability_id)
            span.set_attribute("ois.tenant_id", tenant_id)
            yield span
