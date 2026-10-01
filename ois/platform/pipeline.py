from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .contracts import PlatformIdentity
from .evidence import EvidenceStore
from .learning import LearningStore
from .observability import MetricsStore,TelemetryEvent
from .outcomes import OutcomeStore
from .sources import SourceRegistry
@dataclass(frozen=True)
class PipelineResult:
    source_evidence_id:str
    evidence_id:str
    intelligence_evidence_id:str
    growth_evidence_id:str
    outcome_id:str
    learning_id:str
@dataclass
class ProductionPipeline:
    sources:SourceRegistry
    evidence:EvidenceStore
    outcomes:OutcomeStore
    learning:LearningStore
    metrics:MetricsStore
    def run(self,identity:PlatformIdentity,source_id:str,*,intelligence:Callable[[Any],Any],growth:Callable[[Any],Any],outcome:Callable[[Any],Any],learn:Callable[[Any,Any],str],source_kwargs:dict[str,Any]|None=None)->PipelineResult:
        source_events=self.sources.collect(source_id,identity,**(source_kwargs or {}))
        if not source_events: raise RuntimeError("live source produced no events")
        source=self.evidence.append(identity,"source",[e.payload for e in source_events],live=True)
        intel=self.evidence.append(identity,"intelligence",intelligence(source.payload),parent_ids=(source.evidence_id,),live=True)
        growth_artifact=self.evidence.append(identity,"growth",growth(intel.payload),parent_ids=(intel.evidence_id,),live=True)
        outcome_value=outcome(growth_artifact.payload)
        outcome_event=self.outcomes.record(identity,"production.outcome",outcome_value,parent_ids=(growth_artifact.evidence_id,),verified=True)
        learning_hypothesis=learn(growth_artifact.payload,outcome_event.value)
        learning=self.learning.record(identity,learning_hypothesis,evidence_ids=(source.evidence_id,intel.evidence_id,growth_artifact.evidence_id),outcome_ids=(outcome_event.outcome_id,),confidence=1.0)
        self.metrics.emit(TelemetryEvent("production.loop.completed",identity,{"source":source.evidence_id,"evidence":intel.evidence_id,"growth":growth_artifact.evidence_id,"outcome":outcome_event.outcome_id,"learning":learning.learning_id}))
        return PipelineResult(source.evidence_id,source.evidence_id,intel.evidence_id,growth_artifact.evidence_id,outcome_event.outcome_id,learning.learning_id)
