"""OpenTelemetry integration for the OIS supervisor runtime.

Design rules:
- traces carry execution context but avoid raw tenant identifiers;
- metrics never use unbounded identifiers such as tenant_id or thread_id as labels;
- exporters are configured through environment variables so endpoints are not hard-coded;
- shutdown/flush are explicit lifecycle operations for graceful worker termination.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


@dataclass(frozen=True)
class TelemetryConfig:
    """Runtime-safe telemetry configuration sourced from environment variables."""

    endpoint: str = os.getenv("OIS_OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    insecure: bool = os.getenv("OIS_OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    export_interval_ms: int = int(os.getenv("OIS_OTEL_METRIC_EXPORT_INTERVAL_MS", "15000"))
    environment: str = os.getenv("OIS_ENVIRONMENT", "production")
    service_version: str = os.getenv("OIS_SERVICE_VERSION", "0.0.0")


class OpenTelemetryTelemetryEngine:
    """Installs the process-wide OIS trace and metric providers."""

    def __init__(self, config: TelemetryConfig | None = None) -> None:
        self.config = config or TelemetryConfig()
        self.resource = Resource.create(
            {
                "service.name": "ois.kernel.supervisor",
                "service.namespace": "niceone-obsidian",
                "service.version": self.config.service_version,
                "deployment.environment.name": self.config.environment,
            }
        )
        self._trace_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None

    def initialize(self) -> None:
        """Initialize OTLP/gRPC tracing and metrics exporters exactly once per process."""
        if self._trace_provider is not None or self._meter_provider is not None:
            return

        trace_provider = TracerProvider(resource=self.resource)
        trace_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=self.config.endpoint, insecure=self.config.insecure)
            )
        )
        trace.set_tracer_provider(trace_provider)

        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=self.config.endpoint, insecure=self.config.insecure),
            export_interval_millis=self.config.export_interval_ms,
        )
        meter_provider = MeterProvider(resource=self.resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        self._trace_provider = trace_provider
        self._meter_provider = meter_provider

    def shutdown(self) -> None:
        """Flush and close exporters during graceful process termination."""
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
        if self._trace_provider is not None:
            self._trace_provider.shutdown()
        self._meter_provider = None
        self._trace_provider = None


class SupervisorExecutionTracker:
    """Instruments workflow transitions, executions, and human-approval latency."""

    def __init__(self) -> None:
        self.tracer = trace.get_tracer("ois.supervisor.tracker")
        self.meter = metrics.get_meter("ois.supervisor.metrics")
        self.transition_counter: Counter = self.meter.create_counter(
            "ois_workflow_state_transitions_total",
            description="Workflow state transitions observed by the supervisor.",
            unit="1",
        )
        self.execution_counter: Counter = self.meter.create_counter(
            "ois_workflow_executions_total",
            description="Workflow executions observed by the supervisor.",
            unit="1",
        )
        self.execution_timer: Histogram = self.meter.create_histogram(
            "ois_workflow_execution_duration_seconds",
            description="End-to-end supervisor execution duration.",
            unit="s",
        )
        self.hitl_wait_timer: Histogram = self.meter.create_histogram(
            "ois_hitl_human_latency_seconds",
            description="Time spent waiting for an authorized human approval decision.",
            unit="s",
        )

    @staticmethod
    def _tenant_fingerprint(tenant_id: str) -> str:
        """Return a non-reversible identifier suitable for trace correlation."""
        return hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:16]

    def track_state_transition(
        self,
        tenant_id: str,
        thread_id: str,
        from_state: str,
        to_state: str,
    ) -> None:
        with self.tracer.start_as_current_span("workflow_state_transition") as span:
            span.set_attribute("ois.tenant_fingerprint", self._tenant_fingerprint(tenant_id))
            span.set_attribute("ois.thread_id", thread_id)
            span.set_attribute("ois.transition.from", from_state)
            span.set_attribute("ois.transition.to", to_state)
            self.transition_counter.add(
                1,
                {"from_state": from_state, "to_state": to_state},
            )

    @contextmanager
    def track_execution(
        self,
        tenant_id: str,
        thread_id: str,
        workflow_id: str,
    ) -> Iterator[None]:
        """Create one execution span and bounded-cardinality execution metrics."""
        started = perf_counter()
        with self.tracer.start_as_current_span("ois.workflow.execution") as span:
            span.set_attribute("ois.tenant_fingerprint", self._tenant_fingerprint(tenant_id))
            span.set_attribute("ois.thread_id", thread_id)
            span.set_attribute("ois.workflow_id", workflow_id)
            try:
                yield
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("ois.execution.status", "error")
                raise
            else:
                span.set_attribute("ois.execution.status", "success")
            finally:
                duration = perf_counter() - started
                self.execution_counter.add(1, {"workflow_id": workflow_id})
                self.execution_timer.record(duration, {"workflow_id": workflow_id})

    def record_hitl_resolution_latency(
        self,
        tenant_id: str,
        duration_seconds: float,
        resolution: str,
    ) -> None:
        if duration_seconds < 0:
            raise ValueError("duration_seconds must be non-negative")
        self.hitl_wait_timer.record(
            duration_seconds,
            {"resolution_status": resolution},
        )


__all__ = ["OpenTelemetryTelemetryEngine", "SupervisorExecutionTracker", "TelemetryConfig"]
