from __future__ import annotations

from dataclasses import dataclass

from .models import ExtractedDocument, SourceDocument, WebIntelligenceRequest


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    errors: tuple[str, ...] = ()


class WebIntelligenceValidator:
    """Deterministic validation gate before evidence is accepted."""

    def validate_source(self, source: SourceDocument, request: WebIntelligenceRequest) -> ValidationReport:
        errors: list[str] = []
        if source.status_code < 200 or source.status_code >= 400:
            errors.append(f"unexpected_status:{source.status_code}")
        if source.url != request.url:
            errors.append("source_url_mismatch")
        if not source.body:
            errors.append("empty_source")
        return ValidationReport(not errors, tuple(errors))

    def validate_extraction(self, extracted: ExtractedDocument) -> ValidationReport:
        errors: list[str] = []
        if not extracted.text:
            errors.append("empty_extraction")
        return ValidationReport(not errors, tuple(errors))
