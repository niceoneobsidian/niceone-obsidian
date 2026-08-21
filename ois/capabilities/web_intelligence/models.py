from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class WebIntelligenceRequest:
    """Validated intent for web acquisition and knowledge extraction."""

    url: str
    objective: str = "extract"
    extract_schema: Mapping[str, Any] = field(default_factory=dict)
    preferred_engine: str | None = None
    max_depth: int = 0
    javascript_required: bool = False
    allow_external_links: bool = False
    tenant_id: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceDocument:
    url: str
    status_code: int
    content_type: str
    body: str
    engine: str
    fetched_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    structured: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_url: str
    engine: str
    content_hash: str
    extracted_fields: tuple[str, ...]
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebIntelligenceResult:
    success: bool
    source: SourceDocument | None
    extracted: ExtractedDocument | None
    evidence: EvidenceRecord | None
    engine: str | None
    attempts: int
    validation_errors: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
