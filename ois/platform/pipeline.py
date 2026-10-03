from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .contracts import PlatformIdentity
from .evidence import EvidenceStore
from .learning import LearningStore
from .observability import MetricsStore, TelemetryEvent
from .outcomes import OutcomeStore
from .sources import SourceRegistry


@dataclass(frozen=True)
class PipelineResult:
    source_evidence_id: str
    intelligence_evidence_id: str
    growth_evidence_id: str
    outcome_id: str
    learning_id: str


@dataclass
class ProductionPipeline:
    sources: SourceRegistry
    evidence: EvidenceStore
    outcomes: OutcomeStore
    learning: LearningStore
    metrics: MetricsStore

    def run(
        self,
        identity: PlatformIdentity,
        source_id: str,
        *,
        intelligence: Callable[[Any], Any],
        growth: Callable[[Any], Any],
        outcome: Callable[[Any], Any],
        verify_outcome: Callable[[Any], bool],
        learn: Callable[[Any, Any], str],
        source_kwargs: dict[str, Any] | None = None,
    ) -> PipelineResult:
        source_events = self.sources.collect(source_id, identity, **(source_kwargs or {}))
        if not source_events:
            raise RuntimeError("live source produced no events")

        source_payload = [
            {
                "source_id": event.source_id,
                "artifact_id": event.artifact_id,
                "payload": event.payload,
                "observed_at": str(event.observed_at),
                "content_hash": event.content_hash,
                "provenance": event.provenance,
            }
            for event in source_events
        ]
        source = self.evidence.append(identity, "source", source_payload, live=True)
        intelligence_payloads = [event["payload"] for event in source.payload]
        intelligence_input = (
            intelligence_payloads[0] if len(intelligence_payloads) == 1 else intelligence_payloads
        )
        intel = self.evidence.append(
            identity,
            "intelligence",
            intelligence(intelligence_input),
            parent_ids=(source.evidence_id,),
            live=True,
        )
        growth_artifact = self.evidence.append(
            identity,
            "growth",
            growth(intel.payload),
            parent_ids=(intel.evidence_id,),
            live=True,
        )

        outcome_value = outcome(growth_artifact.payload)
        verified = bool(verify_outcome(outcome_value))
        outcome_event = self.outcomes.record(
            identity,
            "production.outcome",
            outcome_value,
            parent_ids=(growth_artifact.evidence_id,),
            verified=verified,
        )
        if not verified:
            raise RuntimeError("production outcome could not be independently verified")

        learning_hypothesis = learn(growth_artifact.payload, outcome_event.value)
        learning = self.learning.record(
            identity,
            learning_hypothesis,
            evidence_ids=(
                source.evidence_id,
                intel.evidence_id,
                growth_artifact.evidence_id,
            ),
            outcome_ids=(outcome_event.outcome_id,),
            confidence=1.0,
        )
        self.metrics.emit(
            TelemetryEvent(
                "production.loop.completed",
                identity,
                {
                    "source": source.evidence_id,
                    "intelligence": intel.evidence_id,
                    "growth": growth_artifact.evidence_id,
                    "outcome": outcome_event.outcome_id,
                    "learning": learning.learning_id,
                },
            )
        )
        return PipelineResult(
            source.evidence_id,
            intel.evidence_id,
            growth_artifact.evidence_id,
            outcome_event.outcome_id,
            learning.learning_id,
        )
