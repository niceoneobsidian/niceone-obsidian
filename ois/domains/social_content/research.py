"""Governed research interfaces and deterministic evidence handling."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .contracts import ResearchEvidence


@dataclass(frozen=True)
class ResearchResult:
    """Research output with explicit sufficiency and conflict state."""

    evidence: tuple[ResearchEvidence, ...]
    status: str
    conflicts: tuple[str, ...] = ()


class ResearchProvider:
    """Provider-neutral research boundary used by OIS tools."""

    def __init__(self, search: Callable[[str], Iterable[dict[str, Any]]]) -> None:
        self._search = search

    def search(self, query: str, *, require_evidence: bool = False) -> ResearchResult:
        raw = list(self._search(query))
        evidence = tuple(
            ResearchEvidence(
                source_id=str(item.get("source_id", item.get("url", "source"))),
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                excerpt=str(item.get("excerpt", item.get("snippet", ""))),
                authority=float(item.get("authority", 0.5)),
                recency=float(item.get("recency", 0.5)),
                verification=str(item.get("verification", "unverified")),
            )
            for item in raw
        )
        if not evidence:
            return ResearchResult((), "insufficient" if require_evidence else "empty")

        verified = [item for item in evidence if item.verification == "verified"]
        status = "verified" if verified else "unverified"
        return ResearchResult(evidence, status)


def build_research_query(topic: str, audience: str, objective: str) -> str:
    """Create a stable query without embedding platform-specific scraping logic."""

    return f"{topic} | audience: {audience} | objective: {objective}"
