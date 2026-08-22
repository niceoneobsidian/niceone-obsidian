"""Small, deterministic core for governed OIS web research.

Provider/network concerns stay outside this module. The core accepts a SearchProvider,
normalizes results, builds evidence, and validates claims without requiring an LLM or
network access. This keeps the capability contract easy to unit-test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlparse


class ClaimStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTESTED = "CONTESTED"
    NON_FACTUAL = "NON_FACTUAL"


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    max_results: int = 10
    freshness: str | None = None
    language: str | None = None
    region: str | None = None

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if self.max_results < 1:
            raise ValueError("max_results must be positive")


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    source_type: str | None = None

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP(S) URL")


class SearchProvider(Protocol):
    def search(self, request: SearchRequest) -> list[SearchResult]:
        """Return provider results for a validated request."""


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    claim: str
    source: SearchResult
    confidence: float

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty")
        if not self.claim.strip():
            raise ValueError("claim must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    claim: str
    status: ClaimStatus
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchResult:
    request: SearchRequest
    results: tuple[SearchResult, ...]
    evidence: tuple[Evidence, ...]
    status: str


class WebResearchService:
    """Provider-independent research orchestration with deterministic behavior."""

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def research(self, request: SearchRequest) -> ResearchResult:
        results = tuple(self._provider.search(request)[: request.max_results])
        if not results:
            return ResearchResult(request, (), (), "EMPTY")

        evidence = tuple(
            Evidence(
                evidence_id=f"E-{index:03d}",
                claim=result.snippet,
                source=result,
                confidence=1.0 if result.source_type in {"government", "primary"} else 0.75,
            )
            for index, result in enumerate(results, start=1)
            if result.snippet.strip()
        )
        return ResearchResult(request, results, evidence, "SUCCESS")

    @staticmethod
    def check_claim(claim: str, evidence: tuple[Evidence, ...]) -> ClaimCheck:
        normalized = claim.strip().casefold()
        if not normalized:
            return ClaimCheck(claim, ClaimStatus.NON_FACTUAL)

        matches = tuple(
            item.evidence_id
            for item in evidence
            if normalized in item.claim.casefold() or item.claim.casefold() in normalized
        )
        return ClaimCheck(
            claim=claim,
            status=ClaimStatus.VERIFIED if matches else ClaimStatus.UNSUPPORTED,
            evidence_ids=matches,
        )
