from __future__ import annotations

import hashlib
from typing import Any

from .models import SourceDocument


class ProvenanceLedger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, source: SourceDocument, extracted: dict[str, object]) -> dict[str, Any]:
        digest = hashlib.sha256(source.body.encode("utf-8", errors="replace")).hexdigest()
        evidence = {
            "source_url": source.url,
            "engine": source.engine,
            "content_hash": digest,
            "extracted_fields": tuple(sorted(extracted.get("fields", {}).keys()))
            if isinstance(extracted.get("fields"), dict)
            else (),
        }
        self.records.append(evidence)
        return evidence
