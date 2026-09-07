"""Production telemetry bootstrap for OIS worker/supervisor processes."""

from __future__ import annotations

from ois.observability_telemetry import OpenTelemetryTelemetryEngine, SupervisorExecutionTracker


_engine: OpenTelemetryTelemetryEngine | None = None


def initialize_production_telemetry() -> SupervisorExecutionTracker:
    """Initialize exporters before supervisors create telemetry instruments."""
    global _engine
    if _engine is None:
        _engine = OpenTelemetryTelemetryEngine()
        _engine.initialize()
    return SupervisorExecutionTracker()


def shutdown_production_telemetry() -> None:
    """Flush exporters during graceful worker shutdown."""
    if _engine is not None:
        _engine.shutdown()
