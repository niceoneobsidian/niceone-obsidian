from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from uuid import uuid4

from .models import EvidenceRecord, ExtractedDocument, SourceDocument


@dataclass
class ProvenanceLedger:
    records: list[EvidenceRecord] = field(default_factory=list)

    def record(
        self,
        source: SourceDocument,
        extracted: ExtractedDocument,
        confidence: float = 1.0,
    ) -> EvidenceRecord:
        digest = hashlib.sha256(source.body.encode("utf-8", errors="replace")).hexdigest()
        evidence = EvidenceRecord(
            evidence_id=str(uuid4()),
            source_url=source.url,
            engine=source.engine,
            content_hash=digest,
            extracted_fields=tuple(extracted.structured.keys()),
            confidence=max(0.0, min(1.0, confidence)),
            metadata={"fetched_at": source.fetched_at, "content_type": source.content_type},
        )
        self.records.append(evidence)
        return evidence
