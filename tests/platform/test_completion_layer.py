from __future__ import annotations
import pytest
from ois.platform import EvidenceStore,OISControlPlane,ProductionReadinessCertificate,SourceRegistry
from ois.platform.certification import certify
from ois.platform.contracts import PlatformIdentity,QualityGate,VersionRef
from ois.platform.evolution import EvolutionRegistry,EvolutionState
class Adapter:
    source_id="test.live"
    def health(self)->bool:return True
    def collect(self,identity:PlatformIdentity,**kwargs:object):return []
def test_source_registry()->None:
    r=SourceRegistry();r.register(Adapter());assert r.snapshot()==("test.live",);assert r.healthy()==("test.live",)
def test_evidence_tenant_boundary()->None:
    s=EvidenceStore();a=s.append(PlatformIdentity("a"),"source",{"x":1});assert s.verify(a.evidence_id)
    with pytest.raises(PermissionError):s.append(PlatformIdentity("b"),"derived",{},parent_ids=(a.evidence_id,))
def test_learning_requires_evidence()->None:
    from ois.platform.learning import LearningStore
    with pytest.raises(ValueError):LearningStore().record(PlatformIdentity("t"),"h",evidence_ids=(),outcome_ids=(),confidence=.5)
def test_evolution_gates()->None:
    r=EvolutionRegistry();c=r.propose(VersionRef("prompt","1"),{"x":1},evidence_ids=("e",))
    with pytest.raises(PermissionError):r.promote(c.candidate_id)
    c=r.evaluate(c.candidate_id,True);c=r.approve(c.candidate_id);c=r.promote(c.candidate_id);assert c.state is EvolutionState.PROMOTED
def test_readiness()->None:
    cp=OISControlPlane.create();c=certify("EvidenceIntegrityCertificate","evidence","1",[QualityGate("hash",True)],evidence_ids=("e",),production_verified=True);cp.attest(PlatformIdentity("t"),c);r=cp.readiness((c,),"1");assert isinstance(r,ProductionReadinessCertificate);assert r.production_verified
