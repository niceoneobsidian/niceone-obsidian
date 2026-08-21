from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .engines import AcquisitionEngine
from .extraction import ExtractionEngine
from .models import WebIntelligenceRequest, WebIntelligenceResult
from .provenance import ProvenanceLedger
from .routing import AdaptiveRouter
from .sessions import BrowserSessionManager
from .validation import WebIntelligenceValidator


@dataclass
class WebIntelligenceCapability:
    """Single OIS capability facade over replaceable web engines."""

    engines: Sequence[AcquisitionEngine]
    extractor: ExtractionEngine
    router: AdaptiveRouter | None = None
    sessions: BrowserSessionManager = field(default_factory=BrowserSessionManager)
    provenance: ProvenanceLedger = field(default_factory=ProvenanceLedger)
    validator: WebIntelligenceValidator = field(default_factory=WebIntelligenceValidator)

    def __post_init__(self) -> None:
        if self.router is None:
            self.router = AdaptiveRouter(self.engines)

    @property
    def contract(self) -> CapabilityContract:
        return CapabilityContract(
            capability_id="web.intelligence",
            version="0.1.0",
            description="Governed web acquisition, extraction, provenance, validation and adaptive routing.",
            input_schema={"url": "string", "objective": "string", "extract_schema": "object"},
            output_schema={"success": "boolean", "source": "object", "extracted": "object", "evidence": "object"},
            risk_level=RiskLevel.MEDIUM,
            permissions=("network.read", "web.acquire"),
            timeout_seconds=30.0,
            max_retries=0,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        started = datetime.now(timezone.utc).isoformat()
        try:
            input_data = dict(request.input)
            web_request = WebIntelligenceRequest(
                url=str(input_data["url"]),
                objective=str(input_data.get("objective", "extract")),
                extract_schema=input_data.get("extract_schema", {}),
                preferred_engine=input_data.get("preferred_engine"),
                max_depth=int(input_data.get("max_depth", 0)),
                javascript_required=bool(input_data.get("javascript_required", False)),
                allow_external_links=bool(input_data.get("allow_external_links", False)),
                tenant_id=str(input_data.get("tenant_id", "default")),
                metadata=input_data.get("metadata", {}),
            )
            result = self.execute(web_request)
            status = InvocationStatus.SUCCEEDED if result.success else InvocationStatus.FAILED
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=status,
                output=result,
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
                metadata={"attempts": result.attempts, "engine": result.engine},
            )
        except Exception as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
                started_at=started,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def execute(self, request: WebIntelligenceRequest) -> WebIntelligenceResult:
        candidates = self.router.candidates(request) if self.router else []
        attempts = 0
        errors: list[str] = []
        for engine in candidates:
            attempts += 1
            try:
                source = engine.acquire(request)
                source_report = self.validator.validate_source(source, request)
                if not source_report.valid:
                    errors.extend(source_report.errors)
                    self.router.learner.record(engine.name, False)
                    continue
                extracted = self.extractor.extract(source, request)
                extraction_report = self.validator.validate_extraction(extracted)
                if not extraction_report.valid:
                    errors.extend(extraction_report.errors)
                    self.router.learner.record(engine.name, False)
                    continue
                evidence = self.provenance.record(source, extracted)
                self.router.learner.record(engine.name, True)
                return WebIntelligenceResult(
                    success=True,
                    source=source,
                    extracted=extracted,
                    evidence=evidence,
                    engine=engine.name,
                    attempts=attempts,
                    validation_errors=tuple(errors),
                    metadata={"route_score": self.router.learner.score(engine.name)},
                )
            except Exception as exc:
                errors.append(f"{engine.name}:{type(exc).__name__}:{exc}")
                self.router.learner.record(engine.name, False)
        return WebIntelligenceResult(
            success=False,
            source=None,
            extracted=None,
            evidence=None,
            engine=None,
            attempts=attempts,
            validation_errors=tuple(errors),
        )
