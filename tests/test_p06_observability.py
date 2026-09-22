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


from pathlib import Path


def test_vault_enabled_worker_contract_consumes_injected_secrets() -> None:
    manifest = (
        Path(__file__).resolve().parents[1]
        / "production"
        / "k8s"
        / "ois-worker-vault-injection.yaml"
    ).read_text(encoding="utf-8")

    required = (
        'vault.hashicorp.com/agent-inject: "true"',
        'vault.hashicorp.com/agent-inject-secret-supervisor:',
        'vault.hashicorp.com/agent-inject-template-supervisor:',
        "SUPERVISOR_HMAC_SECRET=",
        "test -r /vault/secrets/supervisor.env",
        ". /vault/secrets/supervisor.env",
        "exec python3 -m ois_worker.run",
    )
    for marker in required:
        assert marker in manifest
