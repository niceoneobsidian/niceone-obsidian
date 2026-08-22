from __future__ import annotations

import re
from html import unescape
from typing import Protocol

from .models import SourceDocument, WebIntelligenceRequest


class ExtractionEngine(Protocol):
    name: str

    def extract(
        self, source: SourceDocument, request: WebIntelligenceRequest
    ) -> dict[str, object]: ...


class RuleBasedExtractor:
    name = "rule-based"

    def extract(
        self, source: SourceDocument, request: WebIntelligenceRequest
    ) -> dict[str, object]:
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", source.body, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", unescape(text)).strip()
        return {
            "text": text,
            "fields": {key: None for key in request.extract_schema},
        }
