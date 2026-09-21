from datetime import UTC,datetime
from ois.domains.social_intelligence.source_validation import SourceValidationHarness,FetchBatch
from ois.domains.social_intelligence.evidence import RawEvidence,EvidenceNode,SQLiteEvidenceStore
from ois.domains.social_intelligence.cross_source import CrossSourceResearch
from ois.domains.social_intelligence.media_pipeline import ContentAsset,MediaPipeline,DeterministicMediaAnalyzer
from ois.domains.social_intelligence.outcomes import OutcomeLedger,PredictionSnapshot,OutcomeEvent
from ois.domains.social_intelligence.learning import LearningLoop
from ois.domains.social_intelligence.prediction import predict_content
class Adapter:
    source_id="fixture";connector_version="test.v1"
    def health_check(self):return True
    def fetch(self,*,cursor,since,limit):
        records=({"id":"1","event_type":"post","text":"hello"},{"id":"2","event_type":"post","text":"world"})
        return FetchBatch("fixture","req",records,cursor,"next" if cursor is None else None,1.,99)
def test_g1_source_validation_raw_evidence_cross_source_research():
    r=SourceValidationHarness().validate(Adapter());assert r.authentication_ok and r.normalization_ok and r.pagination_ok
    e=SQLiteEvidenceStore();assert e.append_raw(RawEvidence.from_payload(evidence_id="e1",source_id="s1",source_record_id="1",payload={"text":"a"}))
    assert e.add_node(EvidenceNode("entity:1","entity","Entity 1",("e1",)))
    f=CrossSourceResearch(e).build_finding(claim_id="c1",statement="signal is supported",entity_id="entity:1",evidence_ids=("e1",),source_ids=("s1","s2"),confidence=.8)
    b=CrossSourceResearch(e).research_brief(query="signal",findings=(f,));assert b["confidence"]==.8 and b["evidence_ids"]==("e1",)
def test_g2_media_prediction_outcome_calibration_learning():
    g=MediaPipeline(DeterministicMediaAnalyzer()).process(ContentAsset("c1","video","fixture://c1"));p=predict_content(g);l=OutcomeLedger()
    assert l.record_prediction(PredictionSnapshot("p1","c1",p.model_id,p.model_version,dict(p.metrics),p.confidence,datetime.now(UTC)))
    assert l.record_outcome(OutcomeEvent("o1","c1","overall_performance",.2,datetime.now(UTC),"24h","fixture"))
    assert l.calibrate(metric="overall_performance").sample_count==1
    assert LearningLoop(l).examples(metric="overall_performance")
