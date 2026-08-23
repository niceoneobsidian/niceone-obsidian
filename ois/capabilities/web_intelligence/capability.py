from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ois.kernel.contracts import (
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
)
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .engines import AcquisitionEngine
from .extraction import ExtractionEngine
from .models import WebIntelligenceRequest, WebIntelligenceResult
from .provenance import ProvenanceLedger
from .routing import AdaptiveRouter
from .validation import WebIntelligenceValidator


@dataclass
class WebIntelligenceCapability:
    engines: Sequence[AcquisitionEngine]
    extractor: ExtractionEngine
    router: AdaptiveRouter | None = None
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
            description=(
                "Governed read-only web acquisition, extraction, "
                "validation and provenance."
            ),
            input_schema={
                "url": "string",
                "objective": "string",
                "extract_schema": "object",
            },
            output_schema={
                "success": "boolean",
                "source": "object",
                "extracted": "object",
                "evidence": "object",
            },
            risk_level=RiskLevel.MEDIUM,
            permissions=("network.read", "web.acquire"),
            allowed_domains=(),
            timeout_seconds=10.0,
            max_retries=0,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
        )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        started = datetime.now(UTC).isoformat()
        try:
            data = dict(request.input)
            result = self.execute(
                WebIntelligenceRequest(
                    url=str(data["url"]),
                    objective=str(data.get("objective", "extract")),
                    extract_schema=data.get("extract_schema", {}),
                    preferred_engine=data.get("preferred_engine"),
                    javascript_required=bool(data.get("javascript_required", False)),
                )
            )
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=(
                    InvocationStatus.SUCCEEDED
                    if result.success
                    else InvocationStatus.FAILED
                ),
                output=result,
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
                metadata={
                    "attempts": result.attempts,
                    "engine": result.engine,
                },
            )
        except Exception as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
                started_at=started,
                completed_at=datetime.now(UTC).isoformat(),
            )

    def execute(self, request: WebIntelligenceRequest) -> WebIntelligenceResult:
        if not request.url.startswith(("http://", "https://")):
            return WebIntelligenceResult(
                False, None, None, None, None, 0, ("invalid_url",)
            )

        assert self.router is not None
        errors: list[str] = []
        for attempt, engine in enumerate(
            self.router.candidates(request), start=1
        ):
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
                    True,
                    source,
                    extracted,
                    evidence,
                    engine.name,
                    attempt,
                    tuple(errors),
                )
            except Exception as exc:
                errors.append(f"{engine.name}:{type(exc).__name__}")
                self.router.learner.record(engine.name, False)

        return WebIntelligenceResult(
            False, None, None, None, None, len(errors), tuple(errors)
        )
