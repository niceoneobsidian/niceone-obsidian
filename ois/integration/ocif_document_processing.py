"""Governed OIS boundary for optional OCIF document processing.

The parser is injected: OIS owns authorization and execution evidence, while OCIF
owns document records and the optional parser adapter. No file path or PDF bytes
are accepted directly from an LLM-authored request.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.recovery import RecoveryBackoff
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries import CapabilityRegistry

DocumentProcessor = Callable[[Mapping[str, Any]], Mapping[str, Any]]
MAX_TRANSIENT_RETRIES = 2
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024


class OCIFDocumentProcessingCapability:
    """Authorize one hash-bound extraction through an injected trusted processor."""

    contract = CapabilityContract(
        capability_id="ocif.document.process",
        version="1.0.0",
        description="Process a verified OCIF document artifact through an approved parser.",
        input_schema={
            "type": "object",
            "required": [
                "source_id",
                "capture_id",
                "artifact_id",
                "artifact_sha256",
                "artifact_size_bytes",
                "media_type",
                "options_digest",
                "idempotency_key",
            ],
        },
        output_schema={"type": "object"},
        risk_level=RiskLevel.MEDIUM,
        permissions=("ocif.document.process",),
        allowed_domains=("knowledge_ingestion",),
        timeout_seconds=120.0,
        # Retries are bounded inside this capability. Prevent a second retry loop
        # in the outer runtime by declaring zero kernel-level retries.
        max_retries=0,
        side_effects=SideEffectLevel.REVERSIBLE,
        idempotent=True,
    )

    def __init__(
        self,
        processor: DocumentProcessor,
        *,
        backoff: RecoveryBackoff | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._processor = processor
        self._backoff = backoff or RecoveryBackoff(base_seconds=0.1, max_seconds=1.0)
        self._sleep = sleep

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload = request.input
        required = (
            "source_id",
            "capture_id",
            "artifact_id",
            "artifact_sha256",
            "artifact_size_bytes",
            "media_type",
            "options_digest",
            "idempotency_key",
        )
        missing = [name for name in required if payload.get(name) in (None, "")]
        if missing:
            return self._failure(
                request, "ValueError", "missing required fields: " + ", ".join(missing)
            )

        for field in ("artifact_sha256", "options_digest"):
            value = str(payload[field])
            if len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value):
                return self._failure(request, "ValueError", f"{field} must be a SHA-256 hex digest")
        try:
            size = int(payload["artifact_size_bytes"])
        except (TypeError, ValueError):
            return self._failure(
                request, "ValueError", "artifact_size_bytes must be a positive integer"
            )
        if size <= 0:
            return self._failure(
                request, "ValueError", "artifact_size_bytes must be a positive integer"
            )
        if size > MAX_ARTIFACT_BYTES:
            return self._failure(
                request, "ArtifactTooLarge", "artifact exceeds the configured 50 MiB limit"
            )
        if str(payload["media_type"]).lower() != "application/pdf":
            return self._failure(request, "UnsupportedMediaType", "only application/pdf is enabled")

        result: Mapping[str, Any] | None = None
        for attempt in range(MAX_TRANSIENT_RETRIES + 1):
            try:
                result = self._processor(payload)
                break
            except (TimeoutError, ConnectionError) as exc:
                if attempt >= MAX_TRANSIENT_RETRIES:
                    return self._failure(
                        request, type(exc).__name__, "bounded transient retry limit exhausted"
                    )
                self._sleep(self._backoff.delay(attempt + 1))
            except Exception as exc:
                return self._failure(
                    request, type(exc).__name__, "document processor failed; no automatic retry"
                )

        if result is None:
            return self._failure(request, "ProcessingError", "processor returned no result")
        if (
            str(result.get("artifact_sha256", "")).lower()
            != str(payload["artifact_sha256"]).lower()
        ):
            return self._failure(
                request,
                "ArtifactIdentityError",
                "processor result does not match input artifact hash",
            )
        status = result.get("extraction_status")
        if status not in {"success", "partial", "unsupported", "failed", "quarantined"}:
            return self._failure(
                request, "ContractError", "processor returned an unknown extraction status"
            )

        output = {
            "extraction_status": status,
            "source_id": str(payload["source_id"]),
            "capture_id": str(payload["capture_id"]),
            "artifact_id": str(payload["artifact_id"]),
            "artifact_sha256": str(payload["artifact_sha256"]).lower(),
            "options_digest": str(payload["options_digest"]).lower(),
            "processor_id": str(result.get("processor_id", "unknown")),
            "processor_version": str(result.get("processor_version", "unknown")),
            "output_refs": list(result.get("output_refs", [])),
            "warnings": list(result.get("warnings", [])),
            "idempotency_key": str(payload["idempotency_key"]),
        }
        if status in {"failed", "quarantined", "unsupported"}:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "DocumentProcessingNotAccepted", "message": str(status)},
                output=output,
                metadata={"authorization_boundary": "ois", "capability_version": "1.0.0"},
            )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
            metadata={"authorization_boundary": "ois", "capability_version": "1.0.0"},
        )

    def _failure(
        self, request: InvocationRequest, error_type: str, message: str
    ) -> InvocationResult:
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.FAILED,
            error={"type": error_type, "message": message},
            metadata={"authorization_boundary": "ois", "capability_version": "1.0.0"},
        )


def register_ocif_document_processing_capability(
    registry: CapabilityRegistry,
    processor: DocumentProcessor,
    *,
    backoff: RecoveryBackoff | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> OCIFDocumentProcessingCapability:
    """Register the optional processing capability; caller composes it into OIS policy."""
    capability = OCIFDocumentProcessingCapability(processor, backoff=backoff, sleep=sleep)
    registry.register(capability)
    return capability
