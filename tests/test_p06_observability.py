import pytest

from ois.observability_telemetry import (
    OpenTelemetryTelemetryEngine,
    SupervisorExecutionTracker,
    TelemetryConfig,
)


def test_tenant_fingerprint_is_deterministic_and_not_raw_identifier() -> None:
    tenant_id = "tenant-secret-123"
    fingerprint = SupervisorExecutionTracker._tenant_fingerprint(tenant_id)

    assert fingerprint == SupervisorExecutionTracker._tenant_fingerprint(tenant_id)
    assert tenant_id not in fingerprint
    assert len(fingerprint) == 16


def test_negative_hitl_latency_is_rejected() -> None:
    tracker = SupervisorExecutionTracker()

    with pytest.raises(ValueError, match="non-negative"):
        tracker.record_hitl_resolution_latency("tenant-a", -0.01, "approved")


def test_telemetry_engine_initialize_is_idempotent() -> None:
    engine = OpenTelemetryTelemetryEngine(
        TelemetryConfig(endpoint="http://localhost:4317", export_interval_ms=60_000)
    )

    engine.initialize()
    trace_provider = engine._trace_provider
    meter_provider = engine._meter_provider
    engine.initialize()

    assert engine._trace_provider is trace_provider
    assert engine._meter_provider is meter_provider
    engine.shutdown()
