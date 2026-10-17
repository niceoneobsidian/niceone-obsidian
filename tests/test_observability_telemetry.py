from __future__ import annotations

from ois.observability_telemetry import SupervisorExecutionTracker


def test_tenant_fingerprint_is_stable_and_does_not_expose_identifier() -> None:
    tenant_id = "customer-sensitive-tenant-123"

    fingerprint = SupervisorExecutionTracker._tenant_fingerprint(tenant_id)

    assert fingerprint == SupervisorExecutionTracker._tenant_fingerprint(tenant_id)
    assert len(fingerprint) == 16
    assert tenant_id not in fingerprint


def test_thread_fingerprint_is_stable_and_does_not_expose_identifier() -> None:
    thread_id = "workflow-thread-sensitive-456"

    fingerprint = SupervisorExecutionTracker._thread_fingerprint(thread_id)

    assert fingerprint == SupervisorExecutionTracker._thread_fingerprint(thread_id)
    assert len(fingerprint) == 16
    assert thread_id not in fingerprint
    assert fingerprint != SupervisorExecutionTracker._thread_fingerprint("another-thread")
