"""Governed, versioned capability for importing USIE evidence into OCIF."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import sqlite3
import time
from typing import Any

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.recovery import RecoveryBackoff
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

EnvelopeImporter = Callable[[Mapping[str, Any]], Any]


class OCIFImportCapability:
    """Call a validated OCIF consumer only after OIS policy authorization.

    The consumer is injected to keep OIS independent of OCIF's package/runtime.
    The importer must use a durable OCIFStore and return its ImportResult.
    """

    contract = CapabilityContract(
        capability_id="ocif.import.consume",
        version="1.0.0",
        description="Import one versioned USIE evidence envelope into OCIF.",
        input_schema={"type": "object", "required": ["payload"]},
        output_schema={"type": "object"},
        risk_level=RiskLevel.LOW,
        permissions=("ocif.evidence.import",),
        allowed_domains=("knowledge_ingestion",),
        timeout_seconds=30.0,
        max_retries=2,
        side_effects=SideEffectLevel.REVERSIBLE,
        idempotent=True,
    )

    def __init__(
        self,
        importer: EnvelopeImporter,
        *,
        backoff: RecoveryBackoff | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._importer = importer
        self._backoff = backoff or RecoveryBackoff(base_seconds=0.05, max_seconds=1.0)
        self._sleep = sleep

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload = request.input.get("payload")
        if not isinstance(payload, Mapping):
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "ValueError", "message": "payload must be an object"},
            )
        # Only known transient transport/SQLite-lock failures are retried. The
        # stable request invocation ID is preserved; the importer must be idempotent.
        for attempt in range(self.contract.max_retries + 1):
            try:
                result = self._importer(payload)
                break
            except (TimeoutError, ConnectionError, sqlite3.OperationalError) as exc:
                transient_sqlite_lock = isinstance(exc, sqlite3.OperationalError) and (
                    "locked" in str(exc).lower() or "busy" in str(exc).lower()
                )
                if isinstance(exc, sqlite3.OperationalError) and not transient_sqlite_lock:
                    raise
                if attempt >= self.contract.max_retries:
                    raise
                self._sleep(self._backoff.delay(attempt + 1)
        status = str(getattr(result, "status", ""))
        output = {
            "status": status,
            "source_id": getattr(result, "source_id", None),
            "capture_id": getattr(result, "capture_id", None),
            "observation_id": getattr(result, "observation_id", None),
            "reason": getattr(result, "reason", None),
        }
        if status not in {"accepted", "duplicate", "rejected"}:
            raise RuntimeError(f"unsupported OCIF importer result status: {status or 'missing'}")
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
            metadata={"contract_version": "0.1.0"},
        )
