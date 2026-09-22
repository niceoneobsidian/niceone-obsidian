from datetime import UTC, datetime

from ois.domains.social_intelligence.cross_source import CrossSourceResearch
from ois.domains.social_intelligence.evidence import (
    EvidenceNode,
    RawEvidence,
    SQLiteEvidenceStore,
)
from ois.domains.social_intelligence.learning import LearningLoop
from ois.domains.social_intelligence.media_pipeline import (
    ContentAsset,
    DeterministicMediaAnalyzer,
    MediaPipeline,
)
from ois.domains.social_intelligence.outcomes import (
    OutcomeEvent,
    OutcomeLedger,
    PredictionSnapshot,
)
from ois.domains.social_intelligence.prediction import predict_content
from ois.domains.social_intelligence.source_validation import (
    FetchBatch,
    SourceValidationHarness,
)


class Adapter:
    source_id = "fixture"
    connector_version = "test.v1"

    def health_check(self) -> bool:
        return True

    def fetch(self, *, cursor: str | None, since: datetime | None, limit: int) -> FetchBatch:
        records = (
            {"id": "1", "event_type": "post", "text": "hello"},
            {"id": "2", "event_type": "post", "text": "world"},
        )
        return FetchBatch(
            "fixture",
            "req",
            records,
            cursor,
            "next" if cursor is None else None,
            1.0,
            99,
        )


def test_g1_source_validation_raw_evidence_cross_source_research() -> None:
    report = SourceValidationHarness().validate(Adapter())
    assert (
        report.authentication_ok
        and report.normalization_ok
        and report.pagination_ok
    )

    evidence = SQLiteEvidenceStore()
    assert evidence.append_raw(
        RawEvidence.from_payload(
            evidence_id="e1",
            source_id="s1",
            source_record_id="1",
            payload={"text": "a"},
        )
    )
    assert evidence.add_node(EvidenceNode("entity:1", "entity", "Entity 1", ("e1",)))

    research = CrossSourceResearch(evidence)
    finding = research.build_finding(
        claim_id="c1",
        statement="signal is supported",
        entity_id="entity:1",
        evidence_ids=("e1",),
        source_ids=("s1", "s2"),
        confidence=0.8,
    )
    brief = research.research_brief(query="signal", findings=(finding,))
    assert brief["confidence"] == 0.8
    assert brief["evidence_ids"] == ("e1",)


def test_g2_media_prediction_outcome_calibration_learning() -> None:
    genome = MediaPipeline(DeterministicMediaAnalyzer()).process(
        ContentAsset("c1", "video", "fixture://c1")
    )
    prediction = predict_content(genome)
    ledger = OutcomeLedger()

    assert ledger.record_prediction(
        PredictionSnapshot(
            "p1",
            "c1",
            prediction.model_id,
            prediction.model_version,
            dict(prediction.metrics),
            prediction.confidence,
            datetime.now(UTC),
        )
    )
    assert ledger.record_outcome(
        OutcomeEvent(
            "o1",
            "c1",
            "overall_performance",
            0.2,
            datetime.now(UTC),
            "24h",
            "fixture",
        )
    )
    assert ledger.calibrate(metric="overall_performance").sample_count == 1
    assert LearningLoop(ledger).examples(metric="overall_performance")
