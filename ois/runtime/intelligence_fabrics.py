from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class MiddlewareContext:
    agent_id: str
    session_id: str
    phase: str
    payload: dict[str, Any] = field(default_factory=dict)


class MiddlewarePipeline:
    def __init__(
        self,
        hooks: list[Callable[[MiddlewareContext], MiddlewareContext]] | None = None,
    ) -> None:
        self._hooks = list(hooks or [])

    def before(self, context: MiddlewareContext) -> MiddlewareContext:
        for hook in self._hooks:
            context = hook(context)
        return context

    def after(self, context: MiddlewareContext) -> MiddlewareContext:
        for hook in reversed(self._hooks):
            context = hook(context)
        return context


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = handler

    def invoke(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](**arguments)


@dataclass(frozen=True)
class ContextRequest:
    objective: str
    evidence: tuple[dict[str, Any], ...] = ()
    memory: tuple[dict[str, Any], ...] = ()
    knowledge: tuple[dict[str, Any], ...] = ()
    token_budget: int = 8192


@dataclass(frozen=True)
class ContextResult:
    messages: tuple[dict[str, Any], ...]
    token_budget: int


class ContextEngine:
    def assemble(self, request: ContextRequest) -> ContextResult:
        items: list[dict[str, Any]] = [{"role": "system", "content": request.objective}]
        for group in (request.evidence, request.memory, request.knowledge):
            items.extend(group)
        return ContextResult(tuple(items), request.token_budget)


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeEngine:
    def __init__(self) -> None:
        self._documents: dict[str, KnowledgeDocument] = {}

    def ingest(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        document = KnowledgeDocument(str(uuid4()), content, dict(metadata or {}))
        self._documents[document.document_id] = document
        return document

    def retrieve(self, query: str, limit: int = 5) -> list[KnowledgeDocument]:
        terms = set(query.lower().split())
        scored = sorted(
            self._documents.values(),
            key=lambda doc: len(terms.intersection(doc.content.lower().split())),
            reverse=True,
        )
        return scored[:limit]


@dataclass(frozen=True)
class ReasoningPattern:
    name: str
    objective_types: tuple[str, ...] = ()
    topology: str = "single"


class ReasoningRegistry:
    def __init__(self) -> None:
        self._patterns: dict[str, ReasoningPattern] = {}

    def register(self, pattern: ReasoningPattern) -> None:
        self._patterns[pattern.name] = pattern

    def select(self, objective_type: str) -> ReasoningPattern | None:
        matches = [
            pattern
            for pattern in self._patterns.values()
            if objective_type in pattern.objective_types
        ]
        return sorted(matches, key=lambda pattern: pattern.name)[0] if matches else None


@dataclass(frozen=True)
class MultimodalArtifact:
    artifact_id: str
    media_type: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MultimodalRuntime:
    def create(
        self,
        media_type: str,
        uri: str,
        metadata: dict[str, Any] | None = None,
    ) -> MultimodalArtifact:
        return MultimodalArtifact(str(uuid4()), media_type, uri, dict(metadata or {}))


@dataclass(frozen=True)
class SocialSignal:
    signal_id: str
    platform: str
    signal_type: str
    value: float
    timestamp: datetime = field(default_factory=utcnow)
    confidence: float = 1.0


class SocialIntelligenceRuntime:
    def __init__(self) -> None:
        self._signals: list[SocialSignal] = []

    def ingest(
        self,
        platform: str,
        signal_type: str,
        value: float,
        confidence: float = 1.0,
    ) -> SocialSignal:
        signal = SocialSignal(
            str(uuid4()), platform, signal_type, value, utcnow(), confidence
        )
        self._signals.append(signal)
        return signal

    def query(
        self,
        platform: str | None = None,
        signal_type: str | None = None,
    ) -> list[SocialSignal]:
        return [
            signal
            for signal in self._signals
            if (platform is None or signal.platform == platform)
            and (signal_type is None or signal.signal_type == signal_type)
        ]


@dataclass(frozen=True)
class LearningCandidate:
    candidate_id: str
    hypothesis: str
    evidence: tuple[str, ...]
    status: str = "proposed"


class LearningRuntime:
    def __init__(self) -> None:
        self._candidates: dict[str, LearningCandidate] = {}

    def propose(self, hypothesis: str, evidence: list[str]) -> LearningCandidate:
        candidate = LearningCandidate(str(uuid4()), hypothesis, tuple(evidence))
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def approve(self, candidate_id: str) -> LearningCandidate:
        candidate = self._candidates[candidate_id]
        if candidate.status != "evaluated":
            raise ValueError("Candidate must be evaluated before approval")
        approved = LearningCandidate(
            candidate.candidate_id,
            candidate.hypothesis,
            candidate.evidence,
            "approved",
        )
        self._candidates[candidate_id] = approved
        return approved

    def mark_evaluated(self, candidate_id: str) -> LearningCandidate:
        candidate = self._candidates[candidate_id]
        evaluated = LearningCandidate(
            candidate.candidate_id,
            candidate.hypothesis,
            candidate.evidence,
            "evaluated",
        )
        self._candidates[candidate_id] = evaluated
        return evaluated
