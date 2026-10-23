from __future__ import annotations

from ois.integration.ocif_document_processing import OCIFDocumentProcessingCapability
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.policy import DefaultPolicyEngine
from ois.registries import CapabilityRegistry


def payload() -> dict[str, object]:
    return {
        "source_id": "source-1",
        "capture_id": "capture-1",
        "artifact_id": "artifact-1",
        "artifact_sha256": "a" * 64,
        "artifact_size_bytes": 1234,
        "media_type": "application/pdf",
        "options_digest": "b" * 64,
        "idempotency_key": "doc-process-1",
    }


def spine(processor, permissions=("ocif.document.process",), sleep=lambda _seconds: None):
    registry = CapabilityRegistry()
    registry.register(OCIFDocumentProcessingCapability(processor, sleep=sleep))
    return OISSpine(registry, policy=DefaultPolicyEngine(allowed_permissions=permissions))


def request() -> SpineRequest:
    return SpineRequest(
        objective="Process an approved, hash-bound PDF artifact",
        capability_id="ocif.document.process",
        capability_version="1.0.0",
        tenant_id="tenant-test",
        input=payload(),
    )


def test_policy_denial_blocks_document_processor() -> None:
    called = False

    def processor(_payload):
        nonlocal called
        called = True
        return {}

    result = spine(processor, permissions=()).submit(request(), invocation_id="denied")
    assert result.status == "denied"
    assert called is False


def test_valid_processor_result_preserves_lineage() -> None:
    def processor(data):
        return {
            "extraction_status": "success",
            "artifact_sha256": data["artifact_sha256"],
            "processor_id": "docling",
            "processor_version": "1.0",
            "output_refs": ["derived/sha256-a.md"],
            "warnings": [],
        }

    result = spine(processor).submit(request(), invocation_id="accepted")
    assert result.status == "succeeded"
    assert result.output["capture_id"] == "capture-1"
    assert result.output["artifact_sha256"] == "a" * 64
    assert result.output["idempotency_key"] == "doc-process-1"


def test_processor_hash_mismatch_fails_closed() -> None:
    def processor(_data):
        return {"extraction_status": "success", "artifact_sha256": "c" * 64}

    result = spine(processor).submit(request(), invocation_id="mismatch")
    assert result.status == "failed"
    assert result.output is None


def test_transient_failure_retries_only_with_bounded_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    def processor(data):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise TimeoutError("temporary")
        return {
            "extraction_status": "partial",
            "artifact_sha256": data["artifact_sha256"],
            "processor_id": "docling",
            "processor_version": "test",
            "output_refs": [],
            "warnings": ["page_provenance_missing"],
        }

    result = spine(processor, sleep=delays.append).submit(request(), invocation_id="retry")
    assert result.status == "succeeded"
    assert attempts == 2
    assert delays == [0.1]


def test_non_pdf_is_rejected_without_processor_call() -> None:
    called = False

    def processor(_data):
        nonlocal called
        called = True
        return {}

    bad = request()
    bad_input = dict(bad.input)
    bad_input["media_type"] = "text/html"
    req = SpineRequest(
        objective=bad.objective,
        capability_id=bad.capability_id,
        capability_version=bad.capability_version,
        tenant_id=bad.tenant_id,
        input=bad_input,
    )
    result = spine(processor).submit(req, invocation_id="unsupported")
    assert result.status == "failed"
    assert called is False


def test_oversized_artifact_is_rejected_without_processor_call() -> None:
    called = False

    def processor(_data):
        nonlocal called
        called = True
        return {}

    bad = request()
    bad_input = dict(bad.input)
    bad_input["artifact_size_bytes"] = 50 * 1024 * 1024 + 1
    req = SpineRequest(
        objective=bad.objective,
        capability_id=bad.capability_id,
        capability_version=bad.capability_version,
        tenant_id=bad.tenant_id,
        input=bad_input,
    )
    result = spine(processor).submit(req, invocation_id="oversized")
    assert result.status == "failed"
    assert called is False
