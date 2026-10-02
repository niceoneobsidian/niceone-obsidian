from ois.platform.contracts import PlatformIdentity
from ois.platform.evidence import EvidenceStore
from ois.platform.learning import LearningStore
from ois.platform.observability import MetricsStore
from ois.platform.outcomes import OutcomeStore
from ois.platform.pipeline import ProductionPipeline
from ois.platform.sources import SourceEvent, SourceRegistry


class Adapter:
    source_id = "live.test"

    def health(self) -> bool:
        return True

    def collect(self, identity: PlatformIdentity, **kwargs: object) -> list[SourceEvent]:
        return [
            SourceEvent(
                self.source_id,
                "raw-1",
                {"signal": 1},
                identity,
                content_hash="source-hash",
                provenance={"adapter": self.source_id},
            )
        ]


def test_production_pipeline_builds_durable_lineage() -> None:
    sources = SourceRegistry()
    sources.register(Adapter())
    pipeline = ProductionPipeline(
        sources,
        EvidenceStore(),
        OutcomeStore(),
        LearningStore(),
        MetricsStore(),
    )
    result = pipeline.run(
        PlatformIdentity("tenant-a"),
        "live.test",
        intelligence=lambda value: {"i": value},
        growth=lambda value: {"g": value},
        outcome=lambda value: {"o": value},
        verify_outcome=lambda value: value == {"o": {"g": {"i": {"signal": 1}}}},
        learn=lambda growth_value, outcome_value: "growth action produced verified outcome",
    )
    assert pipeline.evidence.verify(result.source_evidence_id)
    assert pipeline.evidence.verify(result.intelligence_evidence_id)
    assert pipeline.evidence.verify(result.growth_evidence_id)
    assert pipeline.outcomes.verified("tenant-a")[0].lineage.parent_ids == (
        result.growth_evidence_id,
    )
    assert len(pipeline.learning.list("tenant-a")) == 1
