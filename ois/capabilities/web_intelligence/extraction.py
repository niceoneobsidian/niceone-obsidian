from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Mapping, Protocol

from .models import ExtractedDocument, SourceDocument, WebIntelligenceRequest


class ExtractionEngine(Protocol):
    name: str

    def extract(
        self,
        source: SourceDocument,
        request: WebIntelligenceRequest,
    ) -> ExtractedDocument:
        ...


@dataclass
class RuleBasedExtractor:
    """Safe baseline extractor; AI/LLM extraction is an injectable adapter."""

    name: str = "rule-based"

    def extract(self, source: SourceDocument, request: WebIntelligenceRequest) -> ExtractedDocument:
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", source.body, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        structured: dict[str, Any] = {}
        for key in request.extract_schema:
            structured[key] = None
        return ExtractedDocument(text=text, structured=structured, metadata={"extractor": self.name})
