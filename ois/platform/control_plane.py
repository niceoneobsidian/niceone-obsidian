from __future__ import annotations
from dataclasses import dataclass
from .certification import Certificate,ProductionReadinessCertificate
from .evidence import EvidenceStore
from .evolution import EvolutionRegistry
from .learning import LearningStore
from .observability import MetricsStore,TelemetryEvent
from .outcomes import OutcomeStore
from .sources import SourceRegistry
from .contracts import PlatformIdentity
@dataclass
class OISControlPlane:
    sources:SourceRegistry; evidence:EvidenceStore; outcomes:OutcomeStore; learning:LearningStore; evolution:EvolutionRegistry; metrics:MetricsStore
    @classmethod
    def create(cls)->"OISControlPlane":return cls(SourceRegistry(),EvidenceStore(),OutcomeStore(),LearningStore(),EvolutionRegistry(),MetricsStore())
    def attest(self,identity:PlatformIdentity,certificate:Certificate)->None:self.metrics.emit(TelemetryEvent("production.certificate",identity,{"type":certificate.certificate_type,"verified":certificate.production_verified}))
    def readiness(self,certificates:tuple[Certificate,...],version:str)->ProductionReadinessCertificate:return ProductionReadinessCertificate(version,certificates)
