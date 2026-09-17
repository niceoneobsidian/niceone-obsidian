"""Application-layer contracts for the OIS Social Growth golden path.

The module contains dependency-free protocols and value objects. Adapters may
implement these contracts without coupling the application layer to a provider,
database, model SDK, or publishing platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence

from .state import ExecutionState


class EvidenceRepository(Protocol):
    """Append-only evidence persistence for an execution."""

    def append(
        self,
        execution_id: str,
        category: str,
        payload: dict[str, Any],
    ) -> None: ...


class ExecutionStateRepository(Protocol):
    """Durable execution state persistence."""

    def get(self, execution_id: str) -> ExecutionState | None: ...

    def transition(self, execution_id: str, state: ExecutionState) -> None: ...


class GateName(StrEnum):
    """The ten externally observable OIS production gates."""

    GOLDEN_PATH = "gate_1_golden_path"
    DURABLE_EXECUTION = "gate_2_durable_execution"
    SOCIAL_INTELLIGENCE = "gate_3_social_intelligence"
    CONTENT_INTELLIGENCE = "gate_4_content_intelligence"
    STRATEGY_GENERATION = "gate_5_strategy_generation"
    PUBLISHING = "gate_6_publishing"
    ANALYTICS = "gate_7_analytics"
    EXPERIMENTATION = "gate_8_experimentation"
    LEARNING = "gate_9_learning"
    CONTROLLED_EVOLUTION = "gate_10_controlled_evolution"


class GateStatus(StrEnum):
    """Lifecycle status for a gate run."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class GateEvidence:
    """Evidence emitted by a gate, suitable for append-only storage."""

    evidence_id: str
    gate: GateName
    execution_id: str
    kind: str
    payload: Mapping[str, Any]
    observed_at: datetime
    source: str
    immutable: bool = True


@dataclass(frozen=True, slots=True)
class GateRun:
    """Durable result envelope for one gate within one execution."""

    run_id: str
    execution_id: str
    gate: GateName
    status: GateStatus
    started_at: datetime
    completed_at: datetime | None = None
    evidence: tuple[GateEvidence, ...] = ()
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Objective:
    """User intent entering the OIS control plane."""

    objective_id: str
    statement: str
    audience: str | None = None
    constraints: Mapping[str, Any] = field(default_factory=dict)
    requested_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SocialIntelligence:
    """Normalized audience, competitor, and trend findings."""

    intelligence_id: str
    audience: Sequence[Mapping[str, Any]] = ()
    competitors: Sequence[Mapping[str, Any]] = ()
    trends: Sequence[Mapping[str, Any]] = ()
    source_evidence_ids: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class ContentGenome:
    """Normalized representation of media and its content characteristics."""

    genome_id: str
    media_uri: str
    features: Mapping[str, Any] = field(default_factory=dict)
    source_evidence_ids: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    """Platform-native strategy/content candidate."""

    candidate_id: str
    platform: str
    content: Mapping[str, Any]
    rationale: str
    source_evidence_ids: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    """Provider-confirmed publication identity."""

    publication_id: str
    platform: str
    platform_post_id: str
    published_at: datetime
    canonical_url: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedMetric:
    """Provider-independent performance measurement."""

    metric_name: str
    value: float
    observed_at: datetime
    dimensions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Experiment:
    """Controlled experiment definition."""

    experiment_id: str
    hypothesis: str
    variants: Sequence[StrategyCandidate]
    success_metrics: Sequence[str]


@dataclass(frozen=True, slots=True)
class LearningResult:
    """Attribution and reusable pattern produced from measured results."""

    learning_id: str
    attribution: Mapping[str, Any]
    pattern: Mapping[str, Any]
    recommendation: str
    source_evidence_ids: Sequence[str] = ()


@dataclass(frozen=True, slots=True)
class EvolutionCandidate:
    """Candidate change that can be shadowed, canaried, promoted, or rolled back."""

    candidate_id: str
    change: Mapping[str, Any]
    evaluation_evidence_ids: Sequence[str]
    rollback_plan: Mapping[str, Any]


class GateRunRepository(Protocol):
    """Durable storage for gate runs and their append-only evidence."""

    def create(self, run: GateRun) -> None: ...

    def update(self, run: GateRun) -> None: ...

    def get(self, execution_id: str, gate: GateName) -> GateRun | None: ...

    def append_evidence(self, evidence: GateEvidence) -> None: ...


class SocialIngestionPort(Protocol):
    """Gate 3: ingest and normalize social or web observations."""

    def ingest(self, objective: Objective) -> SocialIntelligence: ...


class MediaAnalysisPort(Protocol):
    """Gate 4: analyze actual media into a Content Genome."""

    def analyze(self, media_uri: str) -> ContentGenome: ...


class StrategyGenerationPort(Protocol):
    """Gate 5: generate multiple platform-native candidates."""

    def generate(
        self,
        objective: Objective,
        intelligence: SocialIntelligence,
        genome: ContentGenome | None = None,
    ) -> Sequence[StrategyCandidate]: ...


class PublishingPort(Protocol):
    """Gate 6: publish through an authenticated platform adapter."""

    def publish(self, candidate: StrategyCandidate) -> PublicationReceipt: ...


class AnalyticsPort(Protocol):
    """Gate 7: fetch and normalize metrics for a publication."""

    def collect(
        self,
        receipt: PublicationReceipt,
    ) -> Sequence[NormalizedMetric]: ...


class ExperimentationPort(Protocol):
    """Gate 8: define, control, and measure variant publication."""

    def define(
        self,
        hypothesis: str,
        variants: Sequence[StrategyCandidate],
        success_metrics: Sequence[str],
    ) -> Experiment: ...

    def compare(self, experiment: Experiment) -> Mapping[str, Any]: ...


class LearningPort(Protocol):
    """Gate 9: attribute results and produce a reusable recommendation."""

    def learn(
        self,
        experiment: Experiment,
        measurements: Mapping[str, Sequence[NormalizedMetric]],
    ) -> LearningResult: ...


class ControlledEvolutionPort(Protocol):
    """Gate 10: evaluate and safely promote or roll back a change."""

    def evaluate(self, learning: LearningResult) -> EvolutionCandidate: ...

    def shadow(self, candidate: EvolutionCandidate) -> GateEvidence: ...

    def canary(self, candidate: EvolutionCandidate) -> GateEvidence: ...

    def promote(self, candidate: EvolutionCandidate) -> GateEvidence: ...

    def rollback(self, candidate: EvolutionCandidate) -> GateEvidence: ...


class GateContract(Protocol):
    """Common executable contract for a gate orchestrator."""

    gate: GateName

    def run(self, execution_id: str, objective: Objective) -> GateRun: ...


ALL_GATES: tuple[GateName, ...] = tuple(GateName)


def all_gates_passed(runs: Sequence[GateRun]) -> bool:
    """Return true only when every canonical gate has a passing run."""

    latest = {run.gate: run for run in runs}
    return (
        set(latest) == set(ALL_GATES)
        and all(latest[gate].status is GateStatus.PASSED for gate in ALL_GATES)
    )
