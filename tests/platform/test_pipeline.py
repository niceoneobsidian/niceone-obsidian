from ois.platform.contracts import PlatformIdentity
from ois.platform.evidence import EvidenceStore
from ois.platform.learning import LearningStore
from ois.platform.observability import MetricsStore
from ois.platform.outcomes import OutcomeStore
from ois.platform.pipeline import ProductionPipeline
from ois.platform.sources import SourceRegistry,SourceEvent
class Adapter:
    source_id="live.test"
    def health(self):return True
    def collect(self,identity,**kwargs):return [SourceEvent(self.source_id,"raw-1",{"signal":1},identity)]
def test_production_pipeline_builds_durable_lineage():
    sources=SourceRegistry();sources.register(Adapter())
    p=ProductionPipeline(sources,EvidenceStore(),OutcomeStore(),LearningStore(),MetricsStore())
    r=p.run(PlatformIdentity("tenant-a"),"live.test",intelligence=lambda x:{"i":x},growth=lambda x:{"g":x},outcome=lambda x:{"o":x},learn=lambda g,o:"growth action produced verified outcome")
    assert r.source_evidence_id
    assert p.evidence.verify(r.evidence_id)
    assert p.outcomes.verified("tenant-a")[0].lineage.parent_ids==(r.growth_evidence_id,)
    assert len(p.learning.list("tenant-a"))==1
